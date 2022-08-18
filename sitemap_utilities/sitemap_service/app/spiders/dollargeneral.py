import csv
import json
import traceback
import urlparse
import time
from collections import OrderedDict

import re
import requests
from lxml import etree

from . import SitemapSpider


class DollargeneralSitemapSpider(SitemapSpider):
    retailer = 'dollargeneral.com'

    start_url = 'https://www.dollargeneral.com/'

    def _get_antiban_headers(self):
        return OrderedDict([
            ('Host', 'www.dollargeneral.com'),
            ('Pragma', 'no-cache'),
            ('Accept-Encoding', 'gzip, deflate'),
            ('Accept-Language', 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4'),
            ('Upgrade-Insecure-Requests', '1'),
            ('User-Agent',
             'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) '
             'Chrome/60.0.3112.113 Safari/537.36'),
            ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'),
            ('Cache-Control', 'no-cache'),
            ('Connection', 'keep-alive')
        ])

    def _get_proxies(self):
        return {
            'http': 'http://proxy_out.contentanalyticsinc.com:60001',
            'https': 'http://proxy_out.contentanalyticsinc.com:60001'
        }

    def task_sitemap_to_item_urls(self, options):
        items_seen = set()

        shelf_urls = self._parse_start_page()

        with open(self.get_file_path_for_result('item_urls.csv'), 'w') as item_urls_file:
            item_urls_csv = csv.writer(item_urls_file)

            while True:
                if not shelf_urls:
                    self.logger.info('All items were scraped')
                    break

                shelf_url = shelf_urls.pop(0)

                self.logger.info('Scraping shelf page: {}'.format(shelf_url))

                response = self._incapsula_request(shelf_url)

                if response:
                    tree = etree.HTML(response.content)

                    item_urls = tree.xpath(".//div[@class='product-list-bar']//a[@class='product-item-link']/@href")

                    self.logger.info('Found {} items at page'.format(len(item_urls)))

                    for item_url in item_urls:
                        if item_url not in items_seen:
                            item_urls_csv.writerow([item_url])
                            items_seen.add(item_url)

                    next_page = tree.xpath(".//a[@title='Next']/@href")

                    if next_page:
                        shelf_urls.append(next_page[0])

    def _parse_start_page(self):
        self.logger.info('Parsing start page')

        start_urls = []

        response = self._incapsula_request(self.start_url)

        if response:
            load_more = re.search(r'var loadMore = ({[^}]*});', response.content)
            if load_more:
                try:
                    data = json.loads(load_more.group(1))

                    for shelf_urls in data.values():
                        if shelf_urls:
                            shelf_urls = re.findall(r'href="([^"]+)"', shelf_urls[0])

                            for shelf_url in shelf_urls:
                                shelf_url = urlparse.urljoin(response.url, shelf_url)

                                start_urls.append(shelf_url)
                except:
                    self.logger.error('Can not parse start page: {}'.format(traceback.format_exc()))

        return start_urls

    def _incapsula_request(self, url):
        for i in range(self.max_retries):
            try:
                session = requests.Session()
                session.proxies = self._get_proxies()
                session.headers = self._get_antiban_headers()

                response = session.get(url, allow_redirects=False, timeout=(2, 60))
            except:
                self.logger.warn(traceback.format_exc())
            else:
                if response.headers.get('Location'):
                    url = response.headers['Location']
                    self.logger.info('Redirect to {}'.format(url))
                elif response.headers.get('X-CDN'):
                    return response
                else:
                    self.logger.info('Retry request')
                    time.sleep(5)
        else:
            self.logger.error('Spider was banned by Incapsula')
