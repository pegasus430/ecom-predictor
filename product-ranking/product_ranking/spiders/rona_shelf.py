# -*- coding: utf-8 -*-

import urllib

from .rona import RonaProductsSpider
from scrapy.http import Request


class RonaShelfPagesSpider(RonaProductsSpider):
    name = 'rona_shelf_urls_products'
    allowed_domains = ["www.rona.ca"]

    STORE_URL = 'https://www.rona.ca/webapp/wcs/stores/servlet/RonaChangeSelectedStoreCmd'

    handle_httpstatus_list = [404, 403, 302]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))

        super(RonaShelfPagesSpider, self).__init__(*args, **kwargs)

        # RONA Home & Garden Nepean, K2G 5X6
        self.store_id = '55550'

        self.default_headers = {
            ':authority': 'www.rona.ca',
            ':scheme': 'https',
            'Host': 'www.rona.ca',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/63.0.3239.132 Safari/537.36',
        }

    def start_requests(self):
        headers = self.default_headers.copy()
        headers[':method'] = 'GET'
        headers[':path'] = '/en'
        headers['upgrade-insecure-requests'] = '1'

        yield Request(
            url='https://www.rona.ca/en',
            callback=self.after_requests,
            headers=headers
        )

    def after_requests(self, response):
        headers = self.default_headers.copy()
        headers[':method'] = 'POST'
        headers[':path'] = '/webapp/wcs/stores/servlet/RonaChangeSelectedStoreCmd'
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        headers['Referer'] = self.product_url

        payload = {
            'redirectURL': self.product_url,
            'physicalStoreExtId': self.store_id,
            'langId': -1,
            'storeId': 10151,
            'catalogId': 10151
        }

        yield Request(
            url=self.STORE_URL,
            method='POST',
            body=urllib.urlencode(payload),
            headers=headers,
            callback=self._start_requests
        )

    def _start_requests(self, response):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      )

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return None
        self.current_page += 1
        return super(RonaShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)
