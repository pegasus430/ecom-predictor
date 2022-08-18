import csv
import requests
import random
import uuid
import re
import time
import traceback

from datetime import datetime
from collections import namedtuple
from urlparse import urljoin, urlparse, parse_qs
from lxml import etree

from . import SitemapSpider, SitemapSpiderError
from app.models import db, Product


class AmazonSitemapSpider(SitemapSpider):
    retailer = 'amazon.com'

    user_agents = [
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.116 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.116 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_3) AppleWebKit/601.4.4 (KHTML, like Gecko) Version/9.0.3 Safari/601.4.4',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.116 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:44.0) Gecko/20100101 Firefox/44.0',
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.109 Safari/537.36'
    ]

    def task_shelf_to_item_urls(self, options):
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

                    while True:
                        self.logger.info('Scraping shelf page: {}'.format(shelf_url))

                        response = requests.get(shelf_url,
                                                params={'fap': 1},  # don't filter adult results
                                                headers={'user-agent': random.choice(self.user_agents)}, timeout=60)

                        self._check_response(response, raise_error=True)

                        tree = etree.HTML(response.content)

                        item_urls = tree.xpath(".//a[contains(@class,'s-access-detail-page')]/@href | "
                                               ".//div[contains(@class,'zg_itemImmersion')]/div/div/a/@href")

                        if not item_urls:
                            dump_filename = uuid.uuid4().get_hex()

                            self.logger.warn('Empty items list, check dump: {}'.format(dump_filename))
                            self._save_response_dump(response, dump_filename)

                        self.logger.info('Found {} items at page'.format(len(item_urls)))

                        for item_url in item_urls:
                            item_urls_writer.writerow([urljoin(response.url, item_url)])

                        next_url = tree.xpath("//*[@id='pagnNextLink']/@href | "
                                              ".//*[contains(@class,'zg_selected')]/following-sibling::*[1]/a/@href")

                        if next_url:
                            shelf_url = urljoin(response.url, next_url[0])
                        else:
                            break
            except:
                self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                failed_urls.append(shelf_url)
        if failed_urls:
            self.save_failed_urls(failed_urls)
            raise SitemapSpiderError('Some urls cannot be processed')

    def _get_amazon_asin(self, url):
        asin = re.search(r'/dp/(\w+)', url, re.I)
        if asin:
            return asin.group(1)

    def _get_amazon_url(self, asin):
        return 'https://www.amazon.com/dp/{}'.format(asin)

    def task_asin_to_upc(self, options):
        urls = options.get('urls', [])
        asins = options.get('asins', [])

        if not urls and not asins:
            raise SitemapSpiderError('Input Amazon URLs or ASINs')

        with open(self.get_file_path_for_result('upcs.csv'), 'w') as upcs_file:
            upcs_writer = csv.writer(upcs_file)

            cache_enabled = True

            header = ['Amazon URL', 'UPC', 'Walmart URL']
            if options.get('check_upc') or options.get('check_name'):
                header.append('Match Indicator')
                cache_enabled = False

            upcs_writer.writerow(header)

            urls.extend(self._get_amazon_url(asin) for asin in asins)

            failed_urls = []
            for url in urls:
                try:
                    self.logger.info('Processing url: {}'.format(url))
                    asin = self._get_amazon_asin(url)
                    upc = None
                    walmart_url = None
                    amazon_name = None
                    walmart_name = None
                    match_indicators = []

                    if cache_enabled:
                        cache_product = self._get_cache_product(asin)

                        if cache_product:
                            upc = cache_product.upc
                            walmart_url = cache_product.walmart_url

                    if not upc:
                        upcitemdb_product = self._get_upcitemdb_product(asin)
                        upc = upcitemdb_product.upc
                        walmart_url = upcitemdb_product.url
                        walmart_name = upcitemdb_product.name

                        if upc:
                            match_indicators.append('{} by upcitemdb.com'.format(upc))

                    if not upc:
                        asinlab_product = self._get_asinlab_product(asin)
                        upc = asinlab_product.upc
                        amazon_name = asinlab_product.name

                        if upc:
                            match_indicators.append('{} by asinlab.com'.format(upc))

                    amazon_product = None

                    if not upc or not walmart_url and options.get('check_upc'):
                        amazon_product = self._get_amazon_product(url=url)
                        amazon_name = amazon_product.name

                        if amazon_product.upcs:
                            for amazon_upc in amazon_product.upcs:
                                walmart_product = self._get_walmart_product(upc=amazon_upc)

                                if walmart_product.upc:
                                    upc = walmart_product.upc
                                    walmart_url = walmart_product.url
                                    walmart_name = walmart_product.name

                                    match_indicators.append('{} by amazon.com'.format(upc))

                                    break

                    if upc and not walmart_url:
                        walmart_product = self._get_walmart_product(upc=upc)
                        walmart_url = walmart_product.url
                        walmart_name = walmart_product.name

                    if options.get('check_name'):
                        if not amazon_name:
                            if amazon_product:
                                amazon_name = amazon_product.name
                            else:
                                amazon_product = self._get_amazon_product(url=url)
                                amazon_name = amazon_product.name

                        if amazon_name and walmart_name:
                            if amazon_name.lower() == walmart_name.lower():
                                match_indicators.append('titles are match: {}'.format(amazon_name.encode('utf-8')))
                            else:
                                match_indicators.append('titles are not match: Amazon "{}", Walmart "{}"'.format(
                                    amazon_name.encode('utf-8'), walmart_name.encode('utf-8')))
                        else:
                            match_indicators.append('one of titles is missing: Amazon "{}", Walmart "{}"'.format(
                                amazon_name.encode('utf-8') or '', walmart_name.encode('utf-8') or ''))

                    self._update_cache_product(asin, upc, walmart_url)

                    row = [url, upc, walmart_url]
                    if options.get('check_upc') or options.get('check_name'):
                        row.append(', '.join(match_indicators))

                    upcs_writer.writerow(row)
                except:
                    self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                    failed_urls.append(url)
            if failed_urls:
                self.save_failed_urls(failed_urls)
                raise SitemapSpiderError('Some urls cannot be processed')

    def _get_amazon_product(self, url=None, asin=None):
        """
        Parse Amazon product page
        """
        AmazonProduct = namedtuple('Product', ['name', 'upcs', 'best_seller_ranks'])

        product_name = None
        product_upcs = None
        best_seller_ranks = []

        if not url and asin:
            url = self._get_amazon_url(asin)

        if url:
            self.logger.info('Parsing Amazon product page: {}'.format(url))

            proxies = {
                'http': 'http://proxy_out.contentanalyticsinc.com:60001',
                'https': 'http://proxy_out.contentanalyticsinc.com:60001'
            }

            for _ in range(self.max_retries):
                try:
                    response = requests.get(url, proxies=proxies, timeout=(2, 60),
                                            headers={
                                                'User-Agent': random.choice(self.user_agents)
                                            })
                except:
                    self.logger.warn('Request error: {}'.format(traceback.format_exc()))
                else:
                    if self._check_response(response, proxies=proxies):
                        html = etree.HTML(response.content)

                        name = html.xpath('.//*[@id="productTitle"]/text()')
                        if name:
                            product_name = name[0].strip()

                        upcs = html.xpath('.//*[starts-with(text(), "UPC")]/following::text()[normalize-space()][1]')
                        if upcs:
                            product_upcs = upcs[0].split()

                        primary_rank = html.xpath('.//*[@id="SalesRank"]/text()[contains(.,"in")]')
                        if primary_rank:
                            primary_rank = re.search(r'#?([\d ,]+) .*in\s*(.+?)\s*\(', primary_rank[0])
                            if primary_rank:
                                best_seller_ranks.append({
                                    'rank': primary_rank.group(1),
                                    'category': primary_rank.group(2).split(' > ')
                                })

                        secondary_ranks = html.xpath('.//*[@id="SalesRank"]//*[@class="zg_hrsr_item"]')
                        for secondary_rank in secondary_ranks:
                            rank = secondary_rank.xpath('./*[@class="zg_hrsr_rank"]/text()')
                            if rank:
                                rank = re.search(r'#?([\d ,]+)', rank[0])
                                if rank:
                                    rank = rank.group(1)

                            category = secondary_rank.xpath('./*[@class="zg_hrsr_ladder"]//a/text()')
                            best_seller_ranks.append({
                                'rank': rank,
                                'category': category
                            })

                    break
        else:
            self.logger.warn('Can not parse Amazon product: url is missing')

        return AmazonProduct(name=product_name, upcs=product_upcs, best_seller_ranks=best_seller_ranks)

    def _get_walmart_product(self, url=None, upc=None):
        """
        Parse Walmart product page
        """
        WalmartProduct = namedtuple('Product', ['name', 'url', 'upc'])

        product_name = None
        product_url = None
        product_upc = None

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:54.0) Gecko/20100101 Firefox/54.0'
        }

        if url:
            product_url = url

            self.logger.info('Parsing Walmart product page: {}'.format(url))

            product_id = urlparse(url).path.split('/')[-1]
            api_url = 'https://www.walmart.com/terra-firma/item/{}'.format(product_id)

            response = requests.get(api_url, headers=headers, timeout=60)

            if self._check_response(response):
                data = response.json()

                selected_product = data.get('payload', {}).get('selected', {}).get('product')

                if selected_product:
                    product = data.get('payload', {}).get('products', {}).get(selected_product)

                    if product:
                        product_upc = product.get('upc')
                        product_name = product.get('productAttributes', {}).get('productName')
        elif upc:
            product_upc = upc

            self.logger.info('Search Walmart product by UPC: {}'.format(upc))

            search_url = 'https://www.walmart.com/search/api/preso?prg=desktop&query={}&page=1&cat_id=0'.format(upc)

            response = requests.get(search_url, headers=headers, timeout=60)

            if self._check_response(response):
                data = response.json()

                items = data.get('items', [])

                if items:
                    product_url = 'https://www.walmart.com/ip/{}'.format(items[0].get('usItemId'))
                    product_name = items[0].get('title')
        else:
            self.logger.warn('Can not parse Walmart product: url and upc are missing')

        return WalmartProduct(name=product_name, url=product_url, upc=product_upc)

    def _get_cache_product(self, asin):
        """
        Check cache
        """
        self.logger.info('Check cache with ASIN: {}'.format(asin))

        product = Product.query.filter_by(asin=asin).first()

        if product:
            return product
        else:
            self.logger.info('Missing cache')

    def _update_cache_product(self, asin, upc, walmart_url=None):
        """
        Update cache
        """
        self.logger.info('Updating cache for ASIN {} with UPC {} and Walmart URL {}'.format(asin, upc, walmart_url))

        product = Product.query.filter_by(asin=asin).first()

        if product:
            product.upc = upc
            product.walmart_url = walmart_url
        else:
            product = Product(upc=upc, asin=asin, walmart_url=walmart_url)
            db.session.add(product)

        db.session.commit()

    def _get_upcitemdb_product(self, asin):
        """
        Request upcitemdb.com API
        """
        UpcItemDbProduct = namedtuple('Product', ['name', 'url', 'upc'])

        product_name = None
        product_url = None
        product_upc = None

        self.logger.info('Search product at upcitemdb.com by ASIN: {}'.format(asin))
        search_url = 'https://api.upcitemdb.com/prod/v1/lookup?asin={}'.format(asin)

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
                product_upc = items[0].get('upc')

                offers = items[0].get('offers', [])

                for offer in offers:
                    if offer.get('merchant') == 'Wal-Mart.com':
                        product_name = offer.get('title')

                        response = requests.get(offer.get('link'), allow_redirects=False)

                        referral = response.headers['Location']
                        referral_parts = urlparse(referral)

                        if referral_parts.netloc == 'www.walmart.com':
                            product_url = 'https://www.walmart.com/ip/{}'.format(referral_parts.path.split('/')[-1])
                        else:
                            params = parse_qs(referral_parts.query)

                            if params.get('murl'):
                                product_url = 'https://www.walmart.com/ip/{}'.format(
                                    urlparse(params['murl'][0]).path.split('/')[-1])

                        break

        return UpcItemDbProduct(name=product_name, url=product_url, upc=product_upc)

    def _get_asinlab_product(self, asin):
        """
        Request asinlab.com
        """
        AsinLabProduct = namedtuple('Product', ['name', 'upc'])

        product_name = None
        product_upc = None

        self.logger.info('Search product at asinlab.com by ASIN: {}'.format(asin))
        search_url = 'http://www.asinlab.com/php/convertfromasin.php?' \
                     'asin_num={}&id_type=UPC&bulk=false&x=false'.format(asin)

        headers = {
            'Referer': 'http://www.asinlab.com/asin-to-upc/'
        }

        response = requests.get(search_url, headers=headers, timeout=60)

        if self._check_response(response):
            html = etree.HTML(response.content)

            upc = html.xpath('.//td[div/text()="{}"]/following-sibling::td[1]/div/text()'.format(asin))

            if upc:
                product_upc = upc[0]

            name = html.xpath('.//td[div/text()="{}"]/following-sibling::td[5]/div/text()'.format(asin))

            if name:
                # Amazon name
                product_name = name[0]

        return AsinLabProduct(name=product_name, upc=product_upc)

    def task_best_seller_rank(self, options):
        missing_options = {'urls'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        item_urls = options.get('urls', [])

        failed_urls = []

        with open(self.get_file_path_for_result('rankings.csv'), 'w') as rankings_file:
            rankings_csv = csv.writer(rankings_file)
            rankings_csv.writerow(['Viewing=[{date} - {date}]'.format(date=datetime.now().strftime('%x'))])
            rankings_csv.writerow(['ASIN', 'Ranking', 'Category Path'])

            for url in item_urls:
                try:
                    asin = self._get_amazon_asin(url)

                    product = self._get_amazon_product(url)

                    if product.best_seller_ranks:
                        for rank in product.best_seller_ranks:
                            rankings_csv.writerow([asin, rank.get('rank')] + rank.get('category', []))
                    else:
                        rankings_csv.writerow([asin])
                except:
                    self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                    failed_urls.append(url)

        if failed_urls:
            self.save_failed_urls(failed_urls)
            raise SitemapSpiderError('Some urls cannot be processed')
