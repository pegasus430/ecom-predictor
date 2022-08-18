from collections import deque
from copy import deepcopy
import csv
import json
import re
from time import sleep
import traceback
from urlparse import urljoin
from urlparse import urlparse
import uuid

from lxml import etree
import requests
from requests.cookies import cookiejar_from_dict

from . import SitemapSpider, SitemapSpiderError


class HomedepotSitemapSpider(SitemapSpider):
    retailer = 'homedepot.com'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:54.0) Gecko/20100101 Firefox/54.0'
    }

    SITEMAP_URL = 'http://www.homedepot.com/sitemap/d/PIP_sitemap.xml'

    # Store id: 915, cookie lasts until 04/2019
    STORE_COOKIE = 'C4%3D915%2BUnion%252FVauxhall%20-%20Vauxhall%2C%20NJ%2B%3A%3BC4_EXP' \
                   '%3D1554845842%3A%3BC24%3D07088%3A%3BC24_EXP%3D1554845842%3A%3BC34%3' \
                   'D31.1%3A%3BC34_EXP%3D1523396261%3A%3BC39%3D1%3B7%3A00-20%3A00%3B2%3' \
                   'B6%3A00-22%3A00%3B3%3B6%3A00-22%3A00%3B4%3B6%3A00-22%3A00%3B5%3B6%3' \
                   'A00-22%3A00%3B6%3B6%3A00-22%3A00%3B7%3B6%3A00-22%3A00%3A%3BC39_EXP%' \
                   '3D1523313442'

    urls_per_file = 1000000

    def task_sitemap_to_item_urls(self, options):
        self.logger.info('Start parsing sitemap: {}'.format(self.SITEMAP_URL))

        products_seen = set()

        urls_counter = 0
        urls_file = open(self._get_products_filename(urls_counter), 'wb')
        urls_csv = csv.writer(urls_file)

        xml_urls = self._parse_sitemap(self.SITEMAP_URL, raise_error=False)

        for xml_url in xml_urls:
            for url in self._parse_sitemap(xml_url, raise_error=False):
                if 'homedepot.com/p/' in url:
                    url = url.encode('utf-8')
                    product_hash = urlparse(url).path.split('/')[-1]

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

        return self.get_file_path_for_result('homedepot_products_{}.csv'.format(index))

    def task_shelf_to_all_item_urls(self, options):
        options['all'] = True

        self.task_shelf_to_item_urls(options)

    def task_shelf_to_item_urls(self, options):
        missing_options = {'urls'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        shelf_urls = options.get('urls', [])

        session = requests.session()
        session.cookies = cookiejar_from_dict({'THD_PERSIST': self.STORE_COOKIE})

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
                        params['Ns'] = 'P_REP_PRC_MODE|1'

                    shelf_tasks = deque([{'url': shelf_url, 'params': params, 'try': 0}])

                    while shelf_tasks:
                        shelf_task = shelf_tasks.pop()
                        shelf_task_url = shelf_task['url']
                        shelf_task_params = shelf_task['params']

                        self.logger.info('Scraping shelf page: {} with params {}'.format(shelf_task_url, shelf_task_params))

                        response = session.get(shelf_task_url, params=shelf_task_params, headers=self.headers, timeout=60)

                        self._check_response(response, raise_error=True, session=session)

                        tree = etree.HTML(response.content)

                        if options.get('all'):
                            try:
                                total = int(tree.xpath('//span[@id="allProdCount"]/text()')[0])
                                if total > 720:
                                    self.logger.info('Shelf page has more than 720 items: {}'.format(total))

                                    min_price = shelf_task_params.get('lowerBound', 0)
                                    max_price = shelf_task_params.get('upperBound')

                                    if not max_price:
                                        max_price = tree.xpath('//div[@id="max-price-list"]//li[last()]/text()')[0]
                                        max_price = re.search('(\d+)', max_price)
                                        if max_price:
                                            max_price = int(max_price.group(1))

                                    if max_price:
                                        shelf_task_low = deepcopy(shelf_task)
                                        shelf_task_low['params']['lowerBound'] = min_price
                                        shelf_task_low['params']['upperBound'] = (min_price + max_price) / 2
                                        shelf_task_low['try'] = 0
                                        shelf_tasks.append(shelf_task_low)

                                        shelf_task_high = deepcopy(shelf_task)
                                        shelf_task_high['params']['lowerBound'] = (min_price + max_price) / 2
                                        shelf_task_high['params']['upperBound'] = max_price
                                        shelf_task_high['try'] = 0
                                        shelf_tasks.append(shelf_task_high)

                                        sleep(1)
                                        continue
                                    else:
                                        self.logger.error('Cannot get max price')
                            except:
                                self.logger.error('Cannot set price range: {}'.format(traceback.format_exc()))

                        item_urls = []

                        js_data = tree.xpath('//script[@type="application/ld+json"]/text()')
                        if js_data:
                            try:
                                data = json.loads(js_data[0])
                                for item in data['mainEntity']['offers']['itemOffered']:
                                    item_urls.append(item['url'])
                            except:
                                self.logger.error('Wrong JSON data: {}'.format(traceback.format_exc()))

                        if not item_urls:
                            links = tree.xpath('//a[@data-podaction="product image"]/@href') or \
                                    tree.xpath('//a[@data-pod-type="pr"]/@href')
                            for link in links:
                                item_urls.append(urljoin(response.url, link))

                        if not item_urls:
                            dump_filename = uuid.uuid4().get_hex()
                            self.logger.warn('Empty items list, check dump: {}'.format(dump_filename))
                            self._save_response_dump(response, dump_filename)

                            if shelf_task['try'] < self.max_retries:
                                shelf_task['try'] += 1
                                shelf_tasks.append(shelf_task)
                                sleep(3)
                                continue

                        self.logger.info('Found {} items at page'.format(len(item_urls)))

                        for item_url in item_urls:
                            if item_url not in item_urls_seen:
                                item_urls_writer.writerow([item_url])
                                item_urls_seen.add(item_url)

                        next_url = tree.xpath("//a[@title='Next']/@href")
                        if next_url:
                            shelf_task_new = deepcopy(shelf_task)
                            shelf_task_new['url'] = urljoin(response.url, next_url[0])
                            shelf_task_new['try'] = 0
                            shelf_tasks.append(shelf_task_new)

                        sleep(1)
            except:
                self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                failed_urls.append(shelf_url)
        if failed_urls:
            self.save_failed_urls(failed_urls)
            raise SitemapSpiderError('Some urls cannot be processed')
