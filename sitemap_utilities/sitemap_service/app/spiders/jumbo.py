import csv
import requests
import uuid
import ssl
import traceback
import time
import re

from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

from lxml import etree

from . import SitemapSpider, SitemapSpiderError


class JumboSitemapSpider(SitemapSpider):
    retailer = 'jumbo.com'

    def task_shelf_to_item_urls(self, options):
        missing_options = {'urls'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        shelf_urls = options.get('urls', [])

        failed_urls = []
        for shelf_url in shelf_urls:
            try:
                page_number = 0

                item_urls_filename = '{}.csv'.format(
                    self._url_to_filename(shelf_url if isinstance(shelf_urls, list) else shelf_urls[shelf_url]))

                with open(self.get_file_path_for_result(item_urls_filename), 'w') as item_urls_file:
                    item_urls_writer = csv.writer(item_urls_file)

                    while True:
                        shelf_url = shelf_url.replace('tags/producten/', 'producten/tags/')
                        self.logger.info('Scraping shelf page: {}, page number: {}'.format(shelf_url, page_number))

                        response = requests.get(shelf_url, params={'PageNumber': page_number}, timeout=60)

                        self._check_response(response, raise_error=True)

                        tree = etree.HTML(response.content)

                        item_urls = tree.xpath(
                            ".//h3[@data-jum-action='ellipsis']/a/@href")

                        if not item_urls:
                            dump_filename = uuid.uuid4().get_hex()

                            self.logger.warn('Empty items list, check dump: {}'.format(dump_filename))
                            self._save_response_dump(response, dump_filename)

                        self.logger.info('Found {} items at page'.format(len(item_urls)))

                        for item_url in item_urls:
                            item_urls_writer.writerow([item_url.split(';')[0]])

                        if len(item_urls) >= 12:
                            page_number += 1
                        else:
                            break
            except:
                self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                failed_urls.append(shelf_url)
        if failed_urls:
            self.save_failed_urls(failed_urls)
            raise SitemapSpiderError('Some urls cannot be processed')


class ClJumboSitemapSpider(SitemapSpider):
    retailer = 'www.jumbo.cl'

    start_page = 'http://www.jumbo.cl/FO/LogonForm'
    session_page = 'http://www.jumbo.cl/FO/CategoryDisplay'
    shelf_url_template = 'http://www.jumbo.cl/FO/PasoDosResultado?{params}'
    product_url_template = 'http://www.jumbo.cl/FO/ProductDisplay?idprod={product_id}'

    def task_sitemap_to_item_urls(self, options):
        session = requests.session()

        self.logger.info('Loading start page')
        start_response = session.get(self.start_page)
        self._check_response(start_response, raise_error=True, session=session)

        self.logger.info('Getting session cookies')
        session_response = session.get(self.session_page)
        self._check_response(session_response, raise_error=True, session=session)

        categories_tree = etree.HTML(start_response.content)
        categories = categories_tree.xpath(".//*[@id='menu']/div/li")

        for category in categories:
            category_name = self._parse_category_name(category)

            subcategories = category.xpath(".//div[@class='col_1']")

            for subcategory in subcategories:
                subcategory_name = self._parse_subcategory_name(subcategory)

                subsubcategories = subcategory.xpath(".//li")

                for subsubcategory in subsubcategories:
                    subsubcategory_name = self._parse_subsubcategory_name(subsubcategory)

                    shelf_url_params = self._parse_shelf_url_params(subsubcategory)

                    if shelf_url_params:
                        shelf_url = self.shelf_url_template.format(params=shelf_url_params)

                        self.logger.info('Scraping shelf page: {}'.format(shelf_url))
                        shelf_response = session.get(shelf_url)

                        if shelf_response.content:
                            shelf_tree = etree.HTML(shelf_response.content)

                            product_urls = self._parse_product_urls(shelf_tree)

                            if product_urls:
                                shelf_filename = u'{} - {} - {}.csv'.format(category_name,
                                                                            subcategory_name,
                                                                            subsubcategory_name)
                                shelf_filename = re.sub(r'\W', '_', shelf_filename)

                                with open(self.get_file_path_for_result(shelf_filename), 'w') as shelf_file:
                                    shelf_csv = csv.writer(shelf_file)

                                    shelf_csv.writerows([url] for url in product_urls)
                            else:
                                self.logger.warn('Product urls are not found')
                        else:
                            self.logger.warn('Empty content')

    def _parse_category_name(self, category):
        category_name = category.xpath("./a/text()")

        if category_name:
            return category_name[0].strip()

    def _parse_subcategory_name(self, subcategory):
        subcategory_name = subcategory.xpath("./h3/a/text()")

        if subcategory_name:
            return subcategory_name[0].strip()

    def _parse_subsubcategory_name(self, subsubcategory):
        subsubcategory_name = subsubcategory.xpath("./a/text()")

        if subsubcategory_name:
            return subsubcategory_name[0].strip()

    def _parse_shelf_url_params(self, subsubcategory):
        shelf_url = subsubcategory.xpath("./a/@href")

        if shelf_url:
            return shelf_url[0].split('?')[-1]

    def _parse_product_urls(self, shelf_tree):
        product_urls = []

        for href in shelf_tree.xpath(".//a[@id='ficha']/@href"):
            product_id = re.search(r'ficha\((\d+),', href)

            if product_id:
                product_urls.append(self.product_url_template.format(product_id=product_id.group(1)))

        return product_urls


class ClJumboNuevoSitemapSpider(SitemapSpider):
    retailer = 'nuevo.jumbo.cl'

    headers = {
        'User-Agent': 'curl/7.51.0',
        'Host': retailer,
        'Accept': '*/*'
    }

    SITEMAP_URL = 'https://nuevo.jumbo.cl/sitemap.xml'

    # http://www.jumbo.cl/FO_IMGS/htmls/modal-verano/js/selector.js
    LOCATIONS = [
        4,   # Curico
        3,   # Talca
        5,   # Valdivia
        10,  # Rancagua
        1,   # Los Andes
        16,  # Vina del Mar
        6,   # Antofagasta
        8,   # Iquique
        7,   # Calama
    ]

    def task_shelf_to_item_urls(self, options):
        missing_options = {'urls'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        session = requests.Session()
        session.mount('https://nuevo.jumbo.cl', TlsAdapter())
        session.headers = {
            'User-Agent': 'curl/7.51.0',
            'Host': 'nuevo.jumbo.cl',
            'Accept': '*/*'
        }

        shelf_urls = options.get('urls', [])

        failed_urls = []
        while shelf_urls:
            shelf_url = shelf_urls.pop(0)

            try:
                shelf_item_urls = set()

                # scrape each store
                for location in self.LOCATIONS:
                    page_number = 1

                    while True:
                        self.logger.info('Scraping shelf page: {}, location: {}, page number: {}'.format(
                            shelf_url, location, page_number))

                        params = {
                            'sc': location,
                            'PageNumber': page_number,
                            'PS': 50
                        }

                        for i in range(0, self.max_retries):
                            try:
                                response = session.get(shelf_url, params=params, timeout=60)
                            except requests.exceptions.SSLError:
                                self.logger.warn('SSL error: {}, try again after {} seconds'.format(
                                    traceback.format_exc(), (i + 1) * 60))
                                time.sleep((i + 1) * 60)
                            else:
                                break

                        if response.status_code == 301:
                            self.logger.info('End of items list reached')

                            break
                        else:
                            self._check_response(response, raise_error=True, session=session)

                        tree = etree.HTML(response.content)

                        item_urls = tree.xpath(".//div[contains(@class, 'product-item')]/@data-uri")

                        if not item_urls:
                            subcategories = tree.xpath(".//div[contains(@class,'search-single-navigator')]//h4/a/@href")

                            if subcategories:
                                self.logger.info('It is category page, adding subcategory urls')
                                subcategories = map(lambda x: x.split('?')[0], subcategories)

                                shelf_url = subcategories.pop(0)
                                shelf_urls.extend(subcategories)
                                continue
                            else:
                                dump_filename = uuid.uuid4().get_hex()

                                self.logger.warn('Empty items list, check dump: {}'.format(dump_filename))
                                self._save_response_dump(response, dump_filename)

                        self.logger.info('Found {} items at page'.format(len(item_urls)))

                        for item_url in item_urls:
                            shelf_item_urls.add(item_url.split(';')[0])

                        if len(item_urls) >= 50:
                            page_number += 1
                        else:
                            break

                item_urls_filename = '{}.csv'.format(
                    self._url_to_filename(shelf_url if isinstance(shelf_urls, list) else shelf_urls[shelf_url]))

                with open(self.get_file_path_for_result(item_urls_filename), 'w') as item_urls_file:
                    item_urls_writer = csv.writer(item_urls_file)
                    item_urls_writer.writerows([url] for url in shelf_item_urls)
            except:
                self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                failed_urls.append(shelf_url)
        if failed_urls:
            self.save_failed_urls(failed_urls)
            raise SitemapSpiderError('Some urls cannot be processed')

    def task_sitemap_to_item_urls(self, options):
        self.logger.info('Start parsing sitemap: {}'.format(self.SITEMAP_URL))

        with open(self.get_file_path_for_result('product_urls.csv'), 'w') as product_urls_file:
            product_urls_csv = csv.writer(product_urls_file)

            products_seen = set()

            for sitemap_url in self._parse_sitemap(self.SITEMAP_URL, follow=False):
                if 'sitemap-produtos-' in sitemap_url:
                    for product_url in self._parse_sitemap(sitemap_url):
                        if product_url not in products_seen:
                            product_urls_csv.writerow([product_url])
                            products_seen.add(product_url)


class TlsAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, ssl_version=ssl.PROTOCOL_TLSv1_2)
