import csv
import json
import traceback
from urlparse import urljoin
import uuid

import requests
from lxml import etree

from . import SitemapSpider, SitemapSpiderError


class SafewaySitemapSpider(SitemapSpider):
    retailer = 'safeway.com'

    default_login = 'laurebaltazar@gmail.com'
    default_password = '12345678'

    item_url = 'https://shop.vons.com/content/shop/vons/en/detail.{id}.html'
    sign_in_url = 'https://shop.vons.com/bin/safeway/login'
    start_url = 'https://shop.vons.com/ecom/shop-by-aisle'

    def task_sitemap_to_item_urls(self, options):
        session = self._sign_in(options)

        item_ids_seen = set()

        shelf_urls = [self.start_url]

        with open(self.get_file_path_for_result('item_urls.csv'), 'w') as item_urls_file:
            item_urls_csv = csv.writer(item_urls_file)

            while True:
                if not shelf_urls:
                    self.logger.info('All items were scraped')
                    break

                shelf_url = shelf_urls.pop(0)

                self.logger.info('Scraping shelf page: {}'.format(shelf_url))

                response = session.get(shelf_url)
                self._check_response(response, session=session)

                tree = etree.HTML(response.content)

                shelf_sub_urls = tree.xpath(".//*[@class='id-NavigationBody']//*/a/@href")

                if shelf_sub_urls:
                    shelf_urls.extend(map(lambda x: urljoin(response.url, x), shelf_sub_urls))
                else:
                    items = self._parse_shelf_page(tree)
                    self.logger.info('Found {} items'.format(len(items)))

                    for item in items:
                        item_id = item['Id']

                        if item_id not in item_ids_seen:
                            item_url = urljoin(response.url, '#state-ui-richInfo_{}'.format(item_id))

                            item_urls_csv.writerow([item_url])
                            item_ids_seen.add(item_id)

    def _parse_shelf_page(self, tree):
        items = tree.xpath(".//script[@type='application/mustache']/text()")
        try:
            return map(lambda x: json.loads(x), items)
        except:
            self.logger.error(traceback)
            return []

    def _sign_in(self, options):
        zip_code = options.get('zip_code')

        if zip_code:
            data = {
                'resourcePath': '/content/shop/vons/en/welcome/jcr:'
                                'content/root/responsivegrid/column_control/par_0/two_column_zip_code_',
                'zipcode': zip_code,
            }
        else:
            login = options.get('login') or self.default_login
            password = options.get('password') or self.default_password

            data = {
                'resourcePath': '/content/shop/vons/en/welcome/sign-in/jcr:'
                                'content/root/responsivegrid/column_control/par_0/sign_in',
                'userId': login,
                'inputPassword': password,
            }

        for i in range(self.max_retries):
            session = requests.Session()

            response = session.post(self.sign_in_url, data=data, allow_redirects=False)
            while response.next:
                for cookie in session.cookies:
                    if cookie.name.startswith('___utm'):
                        del session.cookies[cookie.name]
                response = session.get(response.next.url, allow_redirects=False)
            self._check_response(response, raise_error=True, session=session)

            self.logger.info('Url after sign in: {}'.format(response.url))

            if not zip_code and 'sign-in.error' in response.url:
                raise SitemapSpiderError('Incorrect login or password')

            if zip_code and 'no-service' in response.url:
                raise SitemapSpiderError('Area Not Serviced: {}'.format(zip_code))

            if not response.url.endswith('/welcome.html'):
                break
        else:
            raise SitemapSpiderError('Cannot sign in')

        return session

    def task_sitemap_to_shelf_to_item_urls(self, options):
        session = self._sign_in(options)

        shelf_urls = [self.start_url]

        with open(self.get_file_path_for_result('item_urls.csv'), 'w') as item_urls_file:
            item_urls_csv = csv.writer(item_urls_file)
            item_urls_csv.writerow(['Shelf url', 'Product name', 'Image url', 'Product url'])

            while True:
                if not shelf_urls:
                    self.logger.info('All items were scraped')
                    break

                shelf_url = shelf_urls.pop(0)

                self.logger.info('Scraping shelf page: {}'.format(shelf_url))

                response = session.get(shelf_url)
                self._check_response(response, session=session)

                tree = etree.HTML(response.content)

                shelf_sub_categories = tree.xpath(".//*[@class='id-NavigationBody']//*/a")
                shelf_sub_urls = tree.xpath(".//*[@class='id-NavigationBody']//*/a/@href")

                if len(shelf_sub_categories) != len(shelf_sub_urls):
                    self.logger.warn('Number of sub categories {} not equal number of links {}. Try again'.format(
                        len(shelf_sub_categories), len(shelf_sub_urls)))
                    shelf_urls.insert(0, shelf_url)
                    continue

                if shelf_sub_urls:
                    self.logger.info('Sub categories:\n{}'.format('\n'.join(shelf_sub_urls)))

                    shelf_urls.extend(map(lambda x: urljoin(response.url, x), shelf_sub_urls))
                else:
                    items = self._parse_shelf_page(tree)
                    self.logger.info('Found {} items'.format(len(items)))

                    for item in items:
                        item_url = urljoin(response.url, '#state-ui-richInfo_{}'.format(item['Id']))

                        if item.get('HasImage'):
                            image_url = 'https://shop.vons.com/productimages/200x200/{}_200x200.jpg'.format(item['Id'])
                        else:
                            image_url = None

                        item_description = item.get('Description')
                        if item_description:
                            item_description = item_description.encode('utf-8')

                        item_urls_csv.writerow([shelf_url, item_description, image_url, item_url])

    def task_shelf_to_item_urls(self, options):
        missing_options = {'urls'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        shelf_urls = options.get('urls', [])

        session = self._sign_in(options)

        failed_urls = []
        for shelf_url in shelf_urls:
            try:
                item_urls_filename = '{}.csv'.format(
                    self._url_to_filename(shelf_url if isinstance(shelf_urls, list) else shelf_urls[shelf_url]))

                with open(self.get_file_path_for_result(item_urls_filename), 'w') as item_urls_file:
                    item_urls_writer = csv.writer(item_urls_file)

                    retry = 0
                    while True:
                        self.logger.info('Scraping shelf page: {}'.format(shelf_url))

                        response = session.get(shelf_url)

                        self._check_response(response, session=session)

                        if response.url.endswith('/welcome.html') and retry < self.max_retries:
                            retry += 1
                            session = self._sign_in(options)
                            continue

                        tree = etree.HTML(response.content)

                        item_urls = []

                        js_data = tree.xpath('//input[@name="gridDataSource"]/@value')
                        if js_data:
                            try:
                                data = json.loads(js_data[0])
                                for product in data.get('products', []):
                                    item_urls.append(self.item_url.format(id=product['id']))
                            except:
                                self.logger.error('Wrong JSON data: {}'.format(traceback.format_exc()))

                        if not item_urls:
                            dump_filename = uuid.uuid4().get_hex()
                            self.logger.warn('Empty items list, check dump: {}'.format(dump_filename))
                            self._save_response_dump(response, dump_filename)

                        self.logger.info('Found {} items at page'.format(len(item_urls)))

                        for item_url in item_urls:
                            item_urls_writer.writerow([item_url])

                        break
            except:
                self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                failed_urls.append(shelf_url)
        if failed_urls:
            self.save_failed_urls(failed_urls)
            raise SitemapSpiderError('Some urls cannot be processed')
