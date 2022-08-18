# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, unicode_literals

from product_ranking.spiders.kroger import KrogerProductsSpider
from scrapy.http import Request

import re


class KrogerShelfPagesSpider(KrogerProductsSpider):
    name = 'kroger_shelf_urls_products'
    allowed_domains = ['kroger.com']
    SHELF_URL = 'https://www.kroger.com/search/api/searchAll?start={start}&count={count}&tab=0&taxonomyId={taxonomy}'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)

        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(KrogerShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': '', 'page_number': 1}.copy()

    def _start_requests(self, response):
        match = re.search(r'categoryId=(\d+)', self.product_url) \
                or re.search(r'pl/[\w-]+/(\d+)', self.product_url)
        if match:
            self.url_formatter.defaults['taxonomy'] = match.group(1)
            headers = self._get_antiban_headers()
            meta = self._setup_meta_compatibility()
            meta.update({"taxonomy": match.group(1)})
            headers.update({'content-length': '0'})
            yield Request(url=self.url_formatter.format(self.SHELF_URL),
                          meta=meta,
                          cookies=response.meta['store_cookies'],
                          headers=headers,
                          method="POST")

    def _scrape_next_results_page_link(self, response):
        req = super(KrogerShelfPagesSpider, self)._scrape_next_results_page_link(response)
        if req and req.meta['start'] / self.PAGE_SIZE < self.num_pages:
            return req.replace(url=self.url_formatter.format(
                self.SHELF_URL,
                start=req.meta['start'],
                taxonomy=response.meta['taxonomy'],
                count=self.PAGE_SIZE
            ))
