import csv
import re
import traceback
import unicodedata
import urllib
import uuid
import time
from copy import deepcopy
from urlparse import urlparse

import requests
from lxml import etree

from . import SitemapSpider, SitemapSpiderError
from app.models import db, Product


class JetSitemapSpider(SitemapSpider):
    retailer = 'jet.com'

    SITEMAP_URL = 'https://images.jet.com/node-v3/seo/sitemapindex.xml'

    urls_per_file = 2000000
    max_tries = 10

    START_URL = "https://jet.com"
    SEARCH_URL = "https://jet.com/api/search/"

    def task_sitemap_to_item_urls(self, options):
        self.logger.info('Start parsing sitemap: {}'.format(self.SITEMAP_URL))

        products_seen = set()

        urls_counter = 0
        urls_file = open(self._get_products_filename(urls_counter), 'wb')
        urls_csv = csv.writer(urls_file)

        for url in self._parse_sitemap(self.SITEMAP_URL):
            if 'jet.com/product/' in url:
                product_hash = int(urlparse(url).path.split('/')[-1], 16)

                if product_hash not in products_seen:
                    products_seen.add(product_hash)

                    urls_csv.writerow([url])
                    urls_counter += 1

                    if urls_counter % self.urls_per_file == 0:
                        self.logger.info('{} urls parsed'.format(urls_counter))

                        urls_file.close()
                        urls_file = open(self._get_products_filename(urls_counter), 'wb')
                        urls_csv = csv.writer(urls_file)

        urls_file.close()

    def _get_products_filename(self, urls_counter):
        index = urls_counter/self.urls_per_file + 1

        return self.get_file_path_for_result('jet_products_{}.csv'.format(index))

    def task_shelf_to_all_item_urls(self, options):
        options['all'] = True

        self.task_shelf_to_item_urls(options)

    def _get_session_headers(self):
        return {
            'User-Agent': 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'
        }

    def task_shelf_to_item_urls(self, options):
        missing_options = {'urls'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        shelf_urls = options.get('urls', [])

        session = requests.Session()
        session.headers = self._get_session_headers()

        token = self._get_token(session)
        if not token:
            raise SitemapSpiderError('Can not get CSRF token')

        headers = {
            'x-csrf-token': token,
            'X-Requested-With': 'XMLHttpRequest',
            'content-type': 'application/json'
        }

        failed_urls = []
        for shelf_url in shelf_urls:
            try:
                item_urls_filename = '{}.csv'.format(
                    self._url_to_filename(shelf_url if isinstance(shelf_urls, list) else shelf_urls[shelf_url]))

                with open(self.get_file_path_for_result(item_urls_filename), 'w') as item_urls_file:
                    item_urls_writer = csv.writer(item_urls_file)

                    items_seen = set()

                    params = {
                        'page': 1,
                        'origination': 'none'
                    }

                    search_term = self._get_search_term(shelf_url)

                    if search_term:
                        params['term'] = search_term

                    category = self._get_category(shelf_url)

                    if category:
                        params['origination'] = 'PLP'
                        params['categories'] = category

                    if options.get('all'):
                        params['sort'] = 'price_high_to_low'

                    shelf_tasks = [{'url': self.SEARCH_URL, 'params': params}]

                    while True:
                        if not shelf_tasks:
                            self.logger.info('All items were scraped')
                            break

                        shelf_task = shelf_tasks.pop(0)
                        shelf_task_url = shelf_task['url']
                        shelf_task_params = shelf_task['params']

                        self.logger.info('Scraping shelf page: {} with params {}'.format(shelf_task_url, shelf_task_params))

                        try:
                            response = session.post(shelf_task_url, json=shelf_task_params, headers=headers, timeout=60)

                            self._check_response(response, raise_error=True, session=session)

                            data = response.json()
                        except SitemapSpiderError:
                            raise
                        except:
                            self.logger.error('Request failed: {}'.format(traceback.format_exc()))
                            try_count = shelf_task.get('try_count', 0)

                            if try_count < self.max_tries:
                                shelf_task['try_count'] = try_count + 1
                                shelf_tasks.append(shelf_task)
                        else:
                            items = data.get('result', {}).get('products', [])

                            total = data.get('result', {}).get('totalFull', 0)
                            shelf_items_limit = data.get('result', {}).get('total', 0)

                            if options.get('all') and shelf_task_params.get('page') == 1:
                                parent_category = '|'.join(map(lambda x: x.get('categoryName'),
                                                               data.get('result', {}).get('categoryLevels', [])))

                                sub_categories = filter(lambda x: x.get('parentPath') == parent_category,
                                                        data.get('result', {}).get('categoryFilters', []))

                                if sub_categories and 'prices' not in shelf_task_params:
                                    for sub_category in sub_categories:
                                        shelf_task_sub_category = deepcopy(shelf_task)
                                        shelf_task_sub_category['params']['categories'] = sub_category.get('categoryId')
                                        shelf_tasks.append(shelf_task_sub_category)

                                if total > shelf_items_limit:
                                    self.logger.info('Shelf page has more than {} items: {}'.format(shelf_items_limit, total))

                                    prices = shelf_task_params.get('prices')

                                    if not prices:
                                        min_price = 0
                                        max_price = int(items[0].get('productPrice', {}).get('referencePrice', 0))

                                        # round up to 100000
                                        max_price = max_price + 100000 * (max_price % 100000 > 0) - max_price % 100000
                                    else:
                                        min_price, max_price = map(int, prices.split('~'))

                                    if max_price - min_price > 1:
                                        shelf_task_low = deepcopy(shelf_task)

                                        shelf_task_low['params']['prices'] = '{}~{}'.format(min_price, (min_price + max_price) / 2)
                                        shelf_tasks.append(shelf_task_low)

                                        shelf_task_high = deepcopy(shelf_task)
                                        shelf_task_high['params']['prices'] = '{}~{}'.format((min_price + max_price) / 2, max_price)
                                        shelf_tasks.append(shelf_task_high)

                                        continue

                                    if 'brands' not in shelf_task_params:
                                        self.logger.info('Filter by brands')
                                        brands = data.get('result', {}).get('brandFacets', [])

                                        for brand in brands:
                                            shelf_task_brand = deepcopy(shelf_task)
                                            shelf_task_brand['params']['brands'] = brand.get('name')
                                            shelf_tasks.append(shelf_task_brand)

                                        continue

                                    self.logger.error('Filtering by price and brand returns {} more then {} items, '
                                                      'params: {}'.format(total, shelf_items_limit, shelf_task_params))

                            if not items:
                                dump_filename = uuid.uuid4().get_hex()

                                self.logger.warn('Empty items list, check dump: {}'.format(dump_filename))
                                self._save_response_dump(response, dump_filename)
                            else:
                                self.logger.info('Found {} items at page'.format(len(items)))

                                for item in items:
                                    item_id = item.get('id')

                                    if item_id not in items_seen:
                                        item_title = item.get('title')
                                        item_slug = self._slugify(item_title)
                                        item_url = "https://jet.com/product/{}/{}".format(item_slug, item_id)

                                        item_urls_writer.writerow([item_url])
                                        items_seen.add(item_id)

                                if data.get('result', {}).get('query', {}).get('from', 0)\
                                        + data.get('result', {}).get('query', {}).get('size', 0) < shelf_items_limit:
                                    shelf_task_new = deepcopy(shelf_task)
                                    shelf_task_new['params']['page'] += 1
                                    shelf_tasks.append(shelf_task_new)
            except:
                self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                failed_urls.append(shelf_url)
        if failed_urls:
            self.save_failed_urls(failed_urls)
            raise SitemapSpiderError('Some urls cannot be processed')

    def _get_token(self, session):
        response = session.get(self.START_URL, timeout=20)

        self._check_response(response, raise_error=True, session=session)

        tree = etree.HTML(response.content)

        token = tree.xpath(".//*[@data-id='csrf']/@data-val")

        if token:
            return token[0].replace('"', '')

    def _get_category(self, url):
        category = re.search(r"category=(\d+)", url)

        if not category:
            category = re.search(r"\w/(\d+)\b", url)

        return category.group(1) if category else None

    def _get_search_term(self, url):
        search_term = re.search("term=([\w\s]+)", urllib.unquote(url).decode('utf8'))

        return search_term.group(1) if search_term else None

    def _slugify(self, value):
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
        value = re.sub('[^\w\s-]', '', value).strip()
        return re.sub('[-\s]+', '-', value)

    def task_upc_to_asin(self, options):
        urls = options.get('urls', [])
        upcs = options.get('upcs', [])

        if not urls and not upcs:
            raise SitemapSpiderError('Input Jet URLs or UPCs')

        session = requests.Session()
        session.headers = self._get_session_headers()

        token = self._get_token(session)
        if not token:
            raise SitemapSpiderError('Can not get CSRF token')

        with open(self.get_file_path_for_result('asins.csv'), 'w') as asins_file:
            asins_writer = csv.writer(asins_file)
            asins_writer.writerow(['UPC', 'Jet URL', 'Amazon URL'])

            failed_urls = []
            for url in urls:
                try:
                    self.logger.info('Processing url: {}'.format(url))
                    amazon_url = None
                    data = self._get_upc(url, token, session)

                    if data['upc'] or data['asin']:
                        amazon_url = self._get_amazon_url(data['upc'], data['asin'])

                        if data['upc']:
                            product = Product.query.filter_by(upc=data['upc']).first()
                            if product:
                                product.jet_url = url
                                db.session.commit()
                    else:
                        self.logger.warn('UPC and ASIN were not found')

                    asins_writer.writerow([data['upc'], url, amazon_url])
                except:
                    self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                    failed_urls.append(url)

            for upc in upcs:
                self.logger.info('Processing upc: {}'.format(upc))
                data = self._get_url(upc, token, session)
                amazon_url = self._get_amazon_url(upc, data['asin'])

                if data['url']:
                    product = Product.query.filter_by(upc=upc).first()
                    if product:
                        product.jet_url = data['url']
                        db.session.commit()

                asins_writer.writerow([upc, data['url'], amazon_url])

            if failed_urls:
                self.save_failed_urls(failed_urls)
                raise SitemapSpiderError('Some urls cannot be processed')

    def _get_url(self, upc, token, session):
        result = {
            'url': None,
            'asin': None
        }

        # cache
        product = Product.query.filter_by(upc=upc).first()
        if product and product.jet_url:
            result['url'] = product.jet_url
            result['asin'] = product.asin

            return result

        # jet
        headers = {
            'x-csrf-token': token,
            'X-Requested-With': 'XMLHttpRequest',
        }

        response = session.post(self.SEARCH_URL,
                                json={'term': upc, 'origination': 'none'},
                                headers=headers, timeout=60)

        if self._check_response(response, session=session):
            data = response.json()

            products = data.get('result', {}).get('products')

            if products:
                product = products[0]
                product_id = product.get('id')
                product_title = product.get('title')
                product_slug = self._slugify(product_title)

                result['url'] = 'https://jet.com/product/{}/{}'.format(product_slug, product_id)

                asin = product.get('asin') or None
                if asin and isinstance(asin, list):
                    asin = asin[0]

                result['asin'] = asin

        return result

    def _get_upc(self, url, token, session):
        result = {
            'upc': None,
            'asin': None
        }

        # cache
        product = Product.query.filter_by(jet_url=url).first()
        if product:
            result['upc'] = product.upc
            result['asin'] = product.asin

            return result

        # jet
        product_id = urlparse(url).path.split('/')[-1]
        product_url = 'https://jet.com/api/product/v2'

        headers = {
            'x-csrf-token': token,
            'X-Requested-With': 'XMLHttpRequest',
        }

        response = session.post(product_url,
                                json={'sku': product_id, 'origination': 'none'},
                                headers=headers, timeout=60)

        if self._check_response(response, session=session):
            data = response.json()

            upc = data.get('result', {}).get('upc')
            if upc:
                result['upc'] = upc[-12:].zfill(12)

            asin = data.get('result', {}).get('asin') or None
            if asin and isinstance(asin, list):
                asin = asin[0]

            result['asin'] = asin

        return result

    def _get_asin(self, upc):
        # amazon
        self.logger.info('Search on Amazon')
        search_url = 'https://www.amazon.com/s/ref=nb_sb_noss_1?url=field-keywords={}'.format(upc)

        proxies = {
            'http': 'http://proxy_out.contentanalyticsinc.com:60001',
            'https': 'http://proxy_out.contentanalyticsinc.com:60001'
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:54.0) Gecko/20100101 Firefox/54.0'
        }

        for _ in range(self.max_retries):
            try:
                response = requests.get(search_url, headers=headers, proxies=proxies, timeout=(2, 60))
            except:
                self.logger.warn('Request error: {}'.format(traceback.format_exc()))
            else:
                if self._check_response(response, proxies=proxies):
                    tree = etree.HTML(response.content)

                    asin = tree.xpath(".//@data-asin")

                    if asin:
                        return asin[0]

                break

        # upcitemdb
        self.logger.info('Request UPC item DB')
        search_url = 'https://api.upcitemdb.com/prod/v1/lookup?upc={}'.format(upc)

        headers = {
            'Accept': 'application/json',
            'user_key': '1aa153a55cda7dcb5016bdc96fdbad23',
            'key_type': '3scale'
        }

        response = requests.get(search_url, headers=headers, timeout=60)

        if response.status_code == 429:
            self.logger.warn('Request was limited: {}'.format(response.headers))

            sleep_until = response.headers.get('X-RateLimit-Reset')
            if sleep_until:
                sleep_sec = max(0, int(sleep_until) - time.time())

                self.logger.info('Sleeping {} seconds'.format(sleep_sec))

                time.sleep(sleep_sec)

                response = requests.get(search_url, headers=headers, timeout=60)

        if self._check_response(response):
            data = response.json()

            items = data.get('items')

            if items:
                return items[0].get('asin')

    def _get_amazon_url(self, upc, asin=None):
        # cache
        product = Product.query.filter_by(upc=upc).first()

        if product:
            self.logger.info('Value from cache')
            asin = product.asin
        else:
            if not asin:
                asin = self._get_asin(upc)

            if asin:
                product = Product(upc=upc, asin=asin)
                db.session.add(product)

                db.session.commit()
            else:
                self.logger.warn('ASIN was not found')
                return

        return 'https://www.amazon.com/dp/{}'.format(asin)
