import csv
import inspect
import json
import re
import uuid
import time
import os
import io
from StringIO import StringIO
from copy import deepcopy
from itertools import dropwhile
from urlparse import urljoin, urlparse
from datetime import datetime

import pysftp
import requests
import traceback
import jinja2
from lxml import etree

from . import SitemapSpider, SitemapSpiderError
from app.models import db, Product


class WalmartSitemapSpider(SitemapSpider):
    retailer = 'walmart.com'

    SITEMAP_URL = 'https://www.walmart.com/sitemap_ip.xml'
    STORES_SITEMAP_URL = 'https://www.walmart.com/sitemap_store_main.xml'

    urls_per_file = 2000000

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:54.0) Gecko/20100101 Firefox/54.0'
    }

    def __init__(self, *args, **kwargs):
        super(WalmartSitemapSpider, self).__init__(*args, **kwargs)

        self.stores_cache = {}

    def task_shelf_to_all_item_urls(self, options):
        options['all'] = True

        self.task_shelf_to_item_urls(options)

    def task_shelf_to_item_urls(self, options):
        # TODO: use preso api
        missing_options = {'urls'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        shelf_urls = options.get('urls', [])

        failed_urls = []
        for shelf_url in shelf_urls:
            try:
                item_urls_filename = '{}.csv'.format(
                    self._url_to_filename(shelf_url if isinstance(shelf_urls, list) else shelf_urls[shelf_url]))

                with open(self.get_file_path_for_result(item_urls_filename), 'w') as item_urls_file:
                    item_urls_writer = csv.writer(item_urls_file)

                    item_urls_seen = set()

                    params = {}

                    if options.get('all'):
                        params['sort'] = 'price_high'

                    shelf_tasks = [{'url': shelf_url, 'params': params}]

                    while True:
                        if not shelf_tasks:
                            self.logger.info('All items were scraped')
                            break

                        shelf_task = shelf_tasks.pop(0)
                        shelf_task_url = shelf_task['url']
                        shelf_task_params = shelf_task['params']

                        self.logger.info('Scraping shelf page: {} with params {}'.format(shelf_task_url, shelf_task_params))

                        for i in range(self.max_retries):
                            try:
                                response = requests.get(shelf_task_url, params=shelf_task_params, headers=self.headers,
                                                        timeout=60)
                            except:
                                self.logger.error('Error: {}'.format(traceback.format_exc()))
                                self.logger.info('Try again in {} seconds'.format(i + 1))
                                time.sleep(i + 1)
                            else:
                                break
                        else:
                            raise SitemapSpiderError('Failed after retries')

                        self._check_response(response, raise_error=True)

                        tree = etree.HTML(response.content)

                        if tree.xpath(".//span[contains(@class,'zero-results-message')]"):
                            self.logger.info('No items')
                            continue

                        response_data = self._extract_response_data(response)

                        if response_data:
                            items = response_data.get('preso', {}).get('items', [])

                            if options.get('all'):
                                total = response_data.get('preso', {}).get('requestContext', {}).\
                                    get('itemCount', {}).get('total', 0)

                                if total > 1000:
                                    self.logger.info('Shelf page has more than 1000 items: {}'.format(total))

                                    min_price = shelf_task_params.get('min_price', 0)
                                    max_price = shelf_task_params.get('max_price')

                                    if not max_price:
                                        max_price = int(max(items[0].get('primaryOffer', {}).get('offerPrice', 0),
                                                            items[0].get('primaryOffer', {}).get('maxPrice', 0)))

                                        # round up to hundreds
                                        max_price = max_price + 100 * (max_price % 100 > 0) - max_price % 100

                                    if max_price:
                                        if max_price - min_price <= 1:
                                            raise SitemapSpiderError(
                                                'Spider could not scrape all items: shelf page {} has more then 1000 items '
                                                'with price filters {} - {}'.format(shelf_task_url, min_price, max_price))

                                        shelf_task_low = deepcopy(shelf_task)
                                        shelf_task_low['params']['min_price'] = min_price
                                        shelf_task_low['params']['max_price'] = (min_price + max_price) / 2
                                        shelf_tasks.append(shelf_task_low)

                                        shelf_task_high = deepcopy(shelf_task)
                                        shelf_task_high['params']['min_price'] = (min_price + max_price) / 2
                                        shelf_task_high['params']['max_price'] = max_price
                                        shelf_tasks.append(shelf_task_high)

                                        continue
                                    else:
                                        self.logger.warn('Can not get max price')

                            item_urls = filter(None, map(lambda x: x.get('productPageUrl'), items))
                            next_url = response_data.get('preso', {}).get('pageMetadata', {}).get('canonicalNext')

                            if not next_url:
                                next_url = response_data.get('preso', {}).get('pagination', {}).get('next', {}).get('url')

                                if next_url:
                                    shelf_url_parts = urlparse(shelf_url)
                                    next_url = shelf_url_parts._replace(query=next_url).geturl()
                        else:
                            if options.get('all'):
                                total = tree.xpath(".//*[@class='result-summary-container']/span[text()='products']"
                                                   "/preceding-sibling::span[1]/text()")

                                if total:
                                    total = re.sub('\D', '', total[0])

                                    if total:
                                        total = int(total)

                                        if total > 1000:
                                            self.logger.info('Shelf page has more than 1000 items: {}'.format(total))

                                            min_price = shelf_task_params.get('min_price', 0)
                                            max_price = shelf_task_params.get('max_price')

                                            if not max_price:
                                                max_price = tree.xpath(".//*[@id='searchProductResult']"
                                                                       "//div[@class='price-main-block']"
                                                                       "//span[@class='Price-characteristic']/text()")
                                                if max_price:
                                                    max_price = re.sub('\D', '', max_price[0])

                                                    if max_price:
                                                        max_price = int(max_price) + 1

                                                        # round up to hundreds
                                                        max_price = max_price + 100 * (max_price % 100 > 0) - max_price % 100

                                            if max_price:
                                                if max_price - min_price <= 1:
                                                    raise SitemapSpiderError(
                                                        'Spider could not scrape all items: shelf page {} has more then '
                                                        '1000 items with price filters {} - {}'.format(shelf_task_url,
                                                                                                       min_price,
                                                                                                       max_price))

                                                shelf_task_low = deepcopy(shelf_task)
                                                shelf_task_low['params']['min_price'] = min_price
                                                shelf_task_low['params']['max_price'] = (min_price + max_price) / 2
                                                shelf_tasks.append(shelf_task_low)

                                                shelf_task_high = deepcopy(shelf_task)
                                                shelf_task_high['params']['min_price'] = (min_price + max_price) / 2
                                                shelf_task_high['params']['max_price'] = max_price
                                                shelf_tasks.append(shelf_task_high)

                                                continue
                                            else:
                                                self.logger.warn('Can not get max price')
                                else:
                                    self.logger.warn('Total was not found')

                            item_urls = tree.xpath(".//*[@id='searchProductResult']"
                                                   "//a[contains(@class,'product-title-link')]/@href")
                            next_url = tree.xpath(".//link[@rel='next']/@href")

                        if not item_urls:
                            dump_filename = uuid.uuid4().get_hex()

                            self.logger.warn('Empty items list, check dump: {}'.format(dump_filename))
                            self._save_response_dump(response, dump_filename)

                        self.logger.info('Found {} items at page'.format(len(item_urls)))

                        for item_url in item_urls:
                            item_url = urljoin(response.url, item_url)
                            item_url_hash = hash(item_url)

                            if item_url_hash not in item_urls_seen:
                                item_urls_writer.writerow([item_url])
                                item_urls_seen.add(item_url_hash)

                        if next_url:
                            shelf_task_new = deepcopy(shelf_task)
                            shelf_task_new['url'] = next_url[0] if isinstance(next_url, list) else next_url
                            shelf_tasks.append(shelf_task_new)
            except:
                self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                failed_urls.append(shelf_url)
        if failed_urls:
            self.save_failed_urls(failed_urls)
            raise SitemapSpiderError('Some urls cannot be processed')

    def _extract_response_data(self, response):
        _JS_DATA_RE = re.compile(
            r'window\.__WML_REDUX_INITIAL_STATE__\s*=\s*(\{.+?\})\s*;\s*</script>', re.DOTALL)
        js_data = re.search(_JS_DATA_RE, response.content)

        if js_data:
            text = js_data.group(1)

            try:
                data = json.loads(text)
                return data
            except ValueError:
                pass

    def task_upc_to_asin(self, options):
        urls = options.get('urls', [])
        upcs = options.get('upcs', [])

        if not urls and not upcs:
            raise SitemapSpiderError('Input Walmart URLs or UPCs')

        with open(self.get_file_path_for_result('asins.csv'), 'w') as asins_file:
            asins_writer = csv.writer(asins_file)
            asins_writer.writerow(['UPC', 'Walmart URL', 'Amazon URL'])

            failed_urls = []
            for url in urls:
                try:
                    self.logger.info('Processing url: {}'.format(url))
                    amazon_url = None
                    upc = self._get_upc(url)

                    if upc:
                        amazon_url = self._get_amazon_url(upc)

                        product = Product.query.filter_by(upc=upc).first()
                        if product:
                            product.walmart_url = url
                            db.session.commit()
                    else:
                        self.logger.warn('UPC was not found')

                    asins_writer.writerow([upc, url, amazon_url])
                except:
                    self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                    failed_urls.append(url)

            for upc in upcs:
                self.logger.info('Processing upc: {}'.format(upc))
                url = self._get_url(upc)
                amazon_url = self._get_amazon_url(upc)

                if url:
                    product = Product.query.filter_by(upc=upc).first()
                    if product:
                        product.walmart_url = url
                        db.session.commit()

                asins_writer.writerow([upc, url, amazon_url])

            if failed_urls:
                self.save_failed_urls(failed_urls)
                raise SitemapSpiderError('Some urls cannot be processed')

    def _get_upc(self, url):
        product_id = urlparse(url).path.split('/')[-1]

        # cache
        product = Product.query.filter_by(walmart_url=url).first()
        if not product:
            product_url = 'https://www.walmart.com/ip/{}'.format(product_id)
            product = Product.query.filter_by(walmart_url=product_url).first()
        if product:
            return product.upc

        # walmart
        product_url = 'https://www.walmart.com/terra-firma/item/{}'.format(product_id)

        response = requests.get(product_url, headers=self.headers, timeout=60)

        if self._check_response(response):
            data = response.json()

            product = data.get('payload', {}).get('selected', {}).get('product')

            if product:
                return data.get('payload', {}).get('products', {}).get(product, {}).get('upc')

    def _get_url(self, upc):
        # cache
        product = Product.query.filter_by(upc=upc).first()
        if product and product.walmart_url:
            return product.walmart_url

        # walmart
        search_url = 'https://www.walmart.com/search/api/preso?prg=desktop&query={}&page=1&cat_id=0'.format(upc)

        response = requests.get(search_url, headers=self.headers, timeout=60)

        if self._check_response(response):
            data = response.json()

            items = data.get('items', [])

            if items:
                url = items[0].get('productPageUrl')

                if url:
                    return 'https://www.walmart.com/ip/{}'.format(urlparse(url).path.split('/')[-1])

    def _get_asin(self, upc):
        # amazon
        self.logger.info('Search on Amazon')
        search_url = 'https://www.amazon.com/s/ref=nb_sb_noss_1?url=field-keywords={}'.format(upc)

        proxies = {
            'http': 'http://proxy_out.contentanalyticsinc.com:60001',
            'https': 'http://proxy_out.contentanalyticsinc.com:60001'
        }

        for _ in range(self.max_retries):
            try:
                response = requests.get(search_url, headers=self.headers, proxies=proxies, timeout=(2, 60))
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

    def _get_amazon_url(self, upc):
        # cache
        product = Product.query.filter_by(upc=upc).first()

        if product:
            self.logger.info('Value from cache')
            asin = product.asin
        else:
            asin = self._get_asin(upc)

            if asin:
                product = Product(upc=upc, asin=asin)
                db.session.add(product)

                db.session.commit()
            else:
                self.logger.warn('ASIN was not found')
                return

        return 'https://www.amazon.com/dp/{}'.format(asin)

    def task_item_info(self, options):
        missing_options = {'urls'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        item_urls = options.get('urls', [])
        item_urls_csv = StringIO('\n'.join(item_urls))
        item_urls_csv_filename = 'item_urls_{}.csv'.format(self.request_id)

        item_urls_py = StringIO(self._get_function_body(self._retreive_item_info))
        item_urls_py_filename = 'item_urls_{}.py'.format(self.request_id)

        sftp_server = '54.175.228.114'
        sftp_user = 'sftp'
        sftp_password = 'SelbUjheud'
        sftp_dir = '/ebs-sftp/walmart/walmart'

        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None

        with pysftp.Connection(sftp_server, username=sftp_user, password=sftp_password, cnopts=cnopts) as sftp:
            with sftp.cd(sftp_dir):
                self.logger.info('Writing item urls')
                sftp.putfo(item_urls_csv, item_urls_csv_filename)

                self.logger.info('Writing search script')
                sftp.putfo(item_urls_py, item_urls_py_filename)

                self.logger.info('Search script execution')
                results = sftp.execute('python {sftp_dir}/{script} {sftp_dir}/{urls}'.format(
                    sftp_dir=sftp_dir,
                    script=item_urls_py_filename,
                    urls=item_urls_csv_filename
                ))

                sftp.remove(item_urls_py_filename)

                if results:
                    with open(self.get_file_path_for_result('results.csv'), 'wb') as f:
                        f.writelines(results)

                    sftp.remove(item_urls_csv_filename)
                else:
                    raise SitemapSpiderError('Urls were not found')

    def _get_function_body(self, func):
        source_lines = inspect.getsourcelines(func)[0]
        source_lines = dropwhile(lambda x: x.startswith('@'), source_lines)
        source = ''.join(source_lines)

        pattern = re.compile(r'(async\s+)?def\s+\w+\s*\(.*?\)\s*:\s*(.*)', flags=re.S)
        lines = pattern.search(source).group(2).splitlines()

        if len(lines) == 1:
            return lines[0]
        else:
            indentation = len(lines[1]) - len(lines[1].lstrip())

            return '\n'.join([lines[0]] + [line[indentation:] for line in lines[1:]])

    def _retreive_item_info(self):
        """
        Code for remote execution
        """

        try:
            import sys
            import re

            item_urls = sys.argv[1]
            item_ids = []

            with open(item_urls, 'r') as item_urls_file:
                for item_url in item_urls_file:
                    item_id = item_url.strip().split('/')[-1]
                    item_ids.append(item_id)

            departments = '/ebs-sftp/walmart/walmart/departments/ci_walmart_inbound_en_us.xml'

            with open(departments, 'r') as departments_file:
                for line in departments_file:
                    if '<item>' in line:
                        url = None
                        super_department = 'unnav'
                        department = None
                        category = None
                        vendor_id = None
                        vendor_name = None

                    elif '</item>' in line:
                        if not url or not url.startswith('http'):
                            continue

                        item_id = url.strip().split('/')[-1]

                        if item_id in item_ids:
                            print '"{url}","{super_department}","{department}","{category}","{vendor_id}",' \
                                  '"{vendor_name}"'.format(url=url, super_department=super_department,
                                                           department=department, category=category,
                                                           vendor_id=vendor_id, vendor_name=vendor_name)
                    else:
                        # url and vendor_id
                        pu = re.search('<Product_URL>(.+?)</Product_URL>', line)
                        if pu:
                            url = pu.group(1).split('?')[0]
                            vendor_id = re.search('selectedSellerId=(\d+)', pu.group(1))
                            if vendor_id:
                                vendor_id = vendor_id.group(1)

                        # vendor_name
                        mpn = re.search('<Marketplace_Partner_Name>(.+?)</Marketplace_Partner_Name>', line)
                        if mpn:
                            vendor_name = mpn.group(1)

                        # super_department
                        dnt = re.search('<DEPT_NM_TRANSLATED>(.+?)</DEPT_NM_TRANSLATED>', line)
                        if dnt:
                            super_department = dnt.group(1)

                        # department and category
                        cpcpd = re.search('<CHAR_PRIM_CAT_PATH_DOT>(.+?)</CHAR_PRIM_CAT_PATH_DOT>', line)
                        if cpcpd:
                            cpcpd = cpcpd.group(1).split('.')
                            # first two are 'home page' and super_departnemnt
                            if len(cpcpd) > 2:
                                department = cpcpd[2]
                            if len(cpcpd) > 3:
                                category = cpcpd[3]
        except Exception as e:
            print 'Error: {}'.format(e)

    def task_sitemap_to_item_urls(self, options):
        self.logger.info('Start parsing sitemap: {}'.format(self.SITEMAP_URL))

        urls_counter = 0
        urls_file = open(self._get_products_filename(urls_counter), 'wb')
        urls_csv = csv.writer(urls_file)

        for url in self._parse_sitemap(self.SITEMAP_URL, headers=self.headers):
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

        return self.get_file_path_for_result('walmart_products_{}.csv'.format(index))

    def task_geo_report(self, options):
        missing_options = {'urls', 'stores'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        report_name = options.get('request_name') or 'geo_report'

        with open(self.get_file_path_for_result('{}.csv'.format(report_name)), 'wb') as geo_report_file:
            csv_writer = csv.writer(geo_report_file)
            csv_writer.writerow(['Zip Code', 'Store ID', 'Product Name', 'URL', 'Price', 'Online - In Stock',
                                 'Shipping Available', 'Pickup in Store', 'Pickup Today', 'Buy In Store',
                                 'In Store Only'])

            stores = options.get('stores', [])

            failed_urls = []
            for store in stores:
                zip_code = None
                store_id = None

                if isinstance(store, dict):
                    zip_code = store.get('zip_code')
                    store_id = store.get('store_id')
                elif isinstance(store, (list, tuple)):
                    if len(store) == 1:
                        store_id = store[0],
                    elif len(store) > 1:
                        zip_code = store[0],
                        store_id = store[1]
                else:
                    store_id = store

                if zip_code and not store_id:
                    store_id = self._get_store_id(zip_code)

                if not store_id:
                    self.logger.warn('Missing store id for zip_code: {}'.format(zip_code))
                    continue

                self.logger.info('Loading info for store id: {}'.format(store_id))

                for url in options.get('urls', []):
                    try:
                        product_info = self._get_product_info(url, store_id)

                        if isinstance(product_info.get('name'), unicode):
                            product_info['name'] = product_info['name'].encode('utf-8')

                        csv_writer.writerow([zip_code, store_id,
                                             product_info.get('name'),
                                             url,
                                             product_info.get('price'),
                                             product_info.get('online_in_stock'),
                                             product_info.get('shipping_available'),
                                             product_info.get('pickup_in_store'),
                                             product_info.get('pickup_today'),
                                             product_info.get('buy_in_store'),
                                             product_info.get('in_store_only')])
                    except:
                        self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                        if url not in failed_urls:
                            failed_urls.append(url)
            if failed_urls:
                self.save_failed_urls(failed_urls)
                raise SitemapSpiderError('Some urls cannot be processed')

    def _get_store_id(self, zip_code):
        self.logger.info('Search store for zip code: {}'.format(zip_code))

        store_search_url = 'https://www.walmart.com/store/finder/electrode/api/stores?' \
                           'singleLineAddr={zip_code}&distance=50'.format(zip_code=zip_code)

        response = requests.get(store_search_url, headers=self.headers, timeout=60)

        if self._check_response(response):
            data = response.json()

            stores = data.get('payload', {}).get('storesData', {}).get('stores', [])

            if stores:
                return stores[0].get('id')

    def _get_product_info(self, url, store_id):
        self.logger.debug('Checking store {}: {}'.format(store_id, url))

        product_info = {
            'name': None,
            'price': None,
            'online_in_stock': False,
            'shipping_available': False,
            'pickup_in_store': False,
            'pickup_today': False,
            'buy_in_store': False,
            'in_store_only': False,
            'best_seller_ranks': []
        }

        product_id = urlparse(url).path.split('/')[-1]

        product_url = 'https://www.walmart.com/terra-firma/item/{}'.format(product_id)

        for i in range(self.max_retries):
            try:
                response = requests.get(product_url, headers=self.headers, cookies={'PSID': str(store_id)}, timeout=60)

                if self._check_response(response):
                    data = response.json()

                    product = data.get('payload', {}).get('selected', {}).get('product')

                    if product:
                        product = data.get('payload', {}).get('products', {}).get(product, {})

                        product_info['name'] = product.get('productAttributes', {}).get('productName')

                        offers = product.get('offers')

                        if offers:
                            offer = data.get('payload', {}).get('offers', {}).get(offers[0], {})

                            if offer:
                                product_info['price'] = \
                                    offer.get('pricesInfo', {}).get('priceMap', {}).get('CURRENT', {}).get('price')

                                if offer.get('productAvailability', {}).get('availabilityStatus') == 'IN_STOCK':
                                    offer_type = offer.get('offerInfo').get('offerType')
                                    if offer_type:
                                        product_info['online_in_stock'] = 'ONLINE' in offer_type
                                        product_info['buy_in_store'] = 'STORE' in offer_type
                                        product_info['in_store_only'] = 'ONLINE' not in offer_type

                                    product_info['shipping_available'] = offer.get('fulfillment', {}).get('shippable')

                                    if offer.get('fulfillment', {}).get('pickupable'):
                                        pickup_options = offer.get('fulfillment', {}).get('pickupOptions', [])

                                        for option in pickup_options:
                                            if str(option.get('storeId')) == str(store_id):
                                                if option.get('availability') == 'AVAILABLE':
                                                    product_info['pickup_in_store'] = True

                                                pickup_method = option.get('pickupMethod')

                                                if pickup_method == 'SHIP_TO_STORE':
                                                    product_info['buy_in_store'] = False
                                                    product_info['pickup_in_store'] = True
                                                elif pickup_method == 'PICK_UP_TODAY':
                                                    product_info['pickup_today'] = True

                                                break
                                        else:
                                            self.logger.warn('Missing store {} in pickup options: {}'.format(
                                                store_id, pickup_options))

                                    if not product_info['pickup_in_store']:
                                        product_info['buy_in_store'] = False
                                        product_info['pickup_today'] = False
                        else:
                            self.logger.info('No offers data. Try again in {} seconds'.format(i))
                            time.sleep(i)
                            continue

                        ranks = product.get("itemSalesRanks") or []

                        if ranks:
                            for rank in ranks:
                                product_info['best_seller_ranks'].append({
                                    'rank': rank.get('rank'),
                                    'category': [c.get('name') for c in rank.get('path', [])]
                                })
                        else:
                            self.logger.info('No ranks data. Try again in {} seconds'.format(i))
                            time.sleep(i)
                            continue
            except:
                self.logger.error('Product info error: {}'.format(traceback.format_exc()))
            else:
                break
        else:
            product_info['buy_online'] = 'Item No Longer Available'

        return product_info

    def task_rich_media(self, options):
        missing_options = {'urls', 'server'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        product_urls = options.get('urls', [])

        rich_media_template = self._get_template('walmart/rich_media.xml')

        failed_urls = []
        for product_url in product_urls:
            try:
                product_id = urlparse(product_url).path.split('/')[-1]

                rich_media = self._parse_rich_media(product_id, options)

                if any(rich_media.values()):
                    rich_media_filename = self.get_file_path_for_result('{}.xml'.format(product_id))

                    with io.open(rich_media_filename, 'w', encoding='utf-8') as rich_media_file:
                        rich_media_file.write(rich_media_template.render(
                            item_id=product_id,
                            date=datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                            **rich_media))
                else:
                    self.logger.warn('Product {} has not rich media'.format(product_url))
            except:
                self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                failed_urls.append(product_url)
        if failed_urls:
            self.save_failed_urls(failed_urls)
            raise SitemapSpiderError('Some urls cannot be processed')

    def _get_template(self, name):
        template_loader = jinja2.FileSystemLoader(searchpath=os.path.join(os.getcwd(), 'app', 'templates'))
        template_env = jinja2.Environment(loader=template_loader, trim_blocks=True, lstrip_blocks=True)
        template_env.filters.update({
            'is_list': lambda x: isinstance(x, list),
        })

        return template_env.get_template(name)

    def _parse_rich_media(self, product_id, options):
        self.logger.debug('Scraping rich media for product id: {}'.format(product_id))

        rich_media = {
            'marketing_content': None
        }

        product_url = 'https://www.walmart.com/terra-firma/item/{}'.format(product_id)

        for i in range(self.max_retries):
            try:
                response = requests.get(product_url, headers=self.headers, timeout=60)

                if self._check_response(response):
                    data = response.json()

                    product = data.get('payload', {}).get('selected', {}).get('product')

                    if product:
                        product = data.get('payload', {}).get('idmlMap', {}).get(product, {})

                        marketing_content = product.get('modules', {}).get('SellPointsMarketingContent', {}).\
                            get('sellpointsmarketingcontent', {}).get('displayValue', {})

                        if marketing_content:
                            saved_marketing_content = self._save_images(marketing_content, options, product_id)

                            if saved_marketing_content:
                                rich_media['marketing_content'] = saved_marketing_content

                                rich_media_filename = self.get_file_path_for_result(
                                    '{}_marketing_content.html'.format(product_id))

                                with io.open(rich_media_filename, 'w', encoding='utf-8') as rich_media_file:
                                    rich_media_file.write(saved_marketing_content)
                            else:
                                raise SitemapSpiderError('Can not save images for product id {}'.format(product_id))

                        videos = []

                        for video in product.get('videos') or []:
                            video_url = video.get('versions', {}).get('LARGE')

                            if video_url:
                                video_url = re.sub(r'^/+', '', video_url)

                                videos.append(video_url)

                        if videos:
                            videos_filename = self.get_file_path_for_result('{}_videos.csv'.format(product_id))

                            with open(videos_filename, 'w') as videos_file:
                                videos_csv = csv.writer(videos_file)
                                videos_csv.writerows([video] for video in videos)

                        pdfs = []

                        for document in product.get('modules', {}).get('ProductUserDocuments', {}).values():
                            for values in document.get('values') or []:
                                for value in values:
                                    pdf_url = value.get('url', {}).get('displayValue')

                                    if pdf_url:
                                        pdfs.append(pdf_url)

                        if pdfs:
                            pdfs_filename = self.get_file_path_for_result('{}_pdfs.csv'.format(product_id))

                            with open(pdfs_filename, 'w') as pdfs_file:
                                pdfs_csv = csv.writer(pdfs_file)
                                pdfs_csv.writerows([pdf] for pdf in pdfs)

                        product_tour = product.get('modules', {}).get('ProductTour', {}).get('ProductTour', {}).\
                            get('displayValue', {})

                        if product_tour:
                            product_tour_html = etree.HTML(product_tour)

                            # standard HTML
                            product_tour_images = set(product_tour_html.xpath(".//img/@src"))

                            if not product_tour_images:
                                # webcollage tour
                                data_resources_base = product_tour_html.xpath(".//@data-resources-base")

                                if data_resources_base:
                                    data_resources_base = data_resources_base[0]

                                    json_data = product_tour_html.xpath(".//*[@class='wc-json-data']/text()")
                                    if json_data:
                                        try:
                                            json_data = json.loads(json_data[0])
                                        except:
                                            self.logger.warn('Can not parse webcollage tour JSON: {}'.format(
                                                traceback.format_exc()))
                                        else:
                                            product_tour_images = []

                                            for tour_view in json_data.get('tourViews', []):
                                                tour_image = tour_view.get('viewImage', {}).get('src', {}).get('src')

                                                if tour_image:
                                                    tour_image = re.sub(r'^/+', '', tour_image)

                                                    product_tour_images.append(urljoin(data_resources_base, tour_image))

                            if product_tour_images:
                                product_tour_filename = self.get_file_path_for_result('{}_product_tour.csv'.format(
                                    product_id))

                                with open(product_tour_filename, 'w') as product_tour_file:
                                    product_tour_csv = csv.writer(product_tour_file)
                                    product_tour_csv.writerows([image] for image in product_tour_images)
            except SitemapSpiderError:
                raise
            except:
                self.logger.error('Product info error: {}'.format(traceback.format_exc()))
            else:
                break
        else:
            self.logger.warn('Item No Longer Available')

        return rich_media

    def _save_images(self, html, options, product_id):
        tree = etree.HTML(html)

        image_urls = set(tree.xpath(".//img/@src|.//img/@wcobj"))

        if image_urls:
            try:
                server = options.get('server') or 'dev-test1'

                api_url = 'https://{server}.contentanalyticsinc.com/api/icebox/file?' \
                          'api_key={api_key}'.format(server=server, api_key=self._get_mc_api_key(server))

                response = requests.post(api_url, data={'links[]': image_urls})
                response.raise_for_status()
            except:
                self.logger.error('Can not save images: {}'.format(traceback.format_exc()))

                return None
            else:
                new_image_urls = response.json()

                for image_url in image_urls:
                    if image_url in new_image_urls:
                        html = html.replace(image_url, new_image_urls[image_url])
                    else:
                        self.logger.error('API response has not image url {}: {}'.format(image_url, new_image_urls))

                        return None

                images_filename = self.get_file_path_for_result('{}_images.csv'.format(product_id))

                with open(images_filename, 'a') as images_file:
                    images_csv = csv.writer(images_file)

                    images_csv.writerow(['Original URL', 'New URL'])
                    images_csv.writerows(new_image_urls.iteritems())

        return html

    def task_best_seller_rank(self, options):
        missing_options = {'urls'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        item_urls = options.get('urls', [])

        failed_urls = []

        with open(self.get_file_path_for_result('rankings.csv'), 'w') as rankings_file:
            rankings_csv = csv.writer(rankings_file)
            rankings_csv.writerow(['Viewing=[{date} - {date}]'.format(date=datetime.now().strftime('%x'))])
            rankings_csv.writerow(['Tool ID', 'Ranking', 'Category Path'])

            for url in item_urls:
                try:
                    product = self._get_product_info(url, store_id=5260)
                    sku = urlparse(url).path.split('/')[-1]
                    if product['best_seller_ranks']:
                        for rank in product['best_seller_ranks']:
                            rankings_csv.writerow([sku, rank.get('rank')] + rank.get('category', []))
                    else:
                        rankings_csv.writerow([sku])
                except:
                    self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                    failed_urls.append(url)

        if failed_urls:
            self.save_failed_urls(failed_urls)
            raise SitemapSpiderError('Some urls cannot be processed')

    def task_stores(self, options):
        workers, tasks, output = self._start_workers(self._parse_stores, count=25)

        for store_url in self._parse_sitemap(self.STORES_SITEMAP_URL):
            tasks.put({'url': store_url})

        stores_filename = 'walmart_stores_{}.csv'.format(datetime.now().strftime('%Y-%m-%d'))

        with open(self.get_file_path_for_result(stores_filename), 'w') as stores_file:
            stores_csv = csv.writer(stores_file)
            stores_csv.writerow(['Zip Code', 'Store ID'])

            while True:
                try:
                    result = output.get(block=True, timeout=60)
                    stores_csv.writerow([result.get('zip_code'), result.get('store_id')])
                except:
                    self.logger.info('Finish')
                    break

        self._stop_workers(workers, tasks)

    def _parse_stores(self, tasks, output):
        for task in iter(tasks.get, 'STOP'):
            store_url = task.get('url')

            store_id = re.search(r'/store/(\d+)/[^/]+/details', store_url)

            if store_id:
                store_id = store_id.group(1)
                zip_code = None

                self.logger.info('Loading store: {}'.format(store_url))

                try:
                    response = requests.get(store_url, headers=self.headers, timeout=60)

                    self._check_response(response, raise_error=True)

                    html = etree.HTML(response.content)

                    postal_code = html.xpath(".//*[@itemprop='postalCode']/text()")
                    if postal_code:
                        zip_code = postal_code[0]
                except:
                    self.logger.error('Can not load store {}'.format(store_id))

                result = {'store_id': store_id, 'zip_code': zip_code}

                if task.get('grocery') and zip_code:
                    if zip_code not in self.stores_cache:
                        self.logger.info('Check stores for zip code: {}'.format(zip_code))

                        store_search_url = 'https://grocery.walmart.com/v3/api/serviceAvailability?' \
                                           'postalCode={zip_code}'.format(zip_code=zip_code)

                        try:
                            response = requests.get(store_search_url, headers=self.headers, timeout=60)

                            self._check_response(response, raise_error=True)

                            data = response.json()

                            stores = dict((
                                store.get('dispenseStoreId'),
                                datetime.strptime(store.get('cpManagedStartDate'), '%Y-%m-%d')
                            ) for store in data.get('accessPointList', []))

                            self.stores_cache[zip_code] = stores
                        except:
                            self.logger.error('Can not check zip code {}'.format(zip_code))

                    stores = self.stores_cache.get(zip_code)

                    if stores:
                        result['grocery'] = stores.get(store_id)

                output.put(result)

    def task_stores_grocery(self, options):
        workers, tasks, output = self._start_workers(self._parse_stores, count=50)

        for store_url in self._parse_sitemap(self.STORES_SITEMAP_URL):
            tasks.put({'url': store_url, 'grocery': True})

        stores_filename = 'walmart_stores_grocerypickup_{}.csv'.format(datetime.now().strftime('%Y-%m-%d'))
        stores_coming_filename = 'walmart_stores_grocerypickup_coming_{}.csv'.format(
            datetime.now().strftime('%Y-%m-%d'))

        stores_file = open(self.get_file_path_for_result(stores_filename), 'w')
        stores_coming_file = open(self.get_file_path_for_result(stores_coming_filename), 'w')

        stores_csv = csv.writer(stores_file)
        stores_csv.writerow(['Zip Code', 'Store ID'])

        stores_coming_csv = csv.writer(stores_coming_file)
        stores_coming_csv.writerow(['Zip Code', 'Store ID', 'Coming Date'])

        while True:
            try:
                result = output.get(block=True, timeout=60)
                self.logger.debug(result)

                if result.get('grocery'):
                    if result['grocery'] >= datetime.now():
                        stores_coming_csv.writerow([result.get('zip_code'), result.get('store_id'), result['grocery']])
                    else:
                        stores_csv.writerow([result.get('zip_code'), result.get('store_id')])
            except:
                self.logger.info('Finish')
                break

        stores_file.close()
        stores_coming_file.close()

        self._stop_workers(workers, tasks)
