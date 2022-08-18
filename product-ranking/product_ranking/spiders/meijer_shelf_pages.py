# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import traceback

from .meijer import MeijerProductsSpider
from scrapy.http import Request


class MeijerShelfPagesSpider(MeijerProductsSpider):
    name = 'meijer_shelf_urls_products'

    CATEGORIES_URL = "https://www.meijer.com/catalog/thumbnail_wrapper.jsp" \
                     "?tierId={tier_id}&keyword=&sort=1&rows={rows}&start={start}&facet="

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)

        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))

        super(MeijerShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def start_requests(self):
        yield Request(
            self.STORE_URL,
            callback=self._start_requests
        )

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}.copy()

    def _start_requests(self, response):
        yield Request(
            self.product_url,
            meta=self._setup_meta_compatibility()
        )

    def _scrape_total_matches(self, response):
        total_info = response.xpath(
            "//div[contains(@class, 'list-results')]"
            "//span[@class='pagination-summary' and contains(text(), 'of')]"
            "/following-sibling::span[@class='pagination-number']"
            "//text()").extract()

        try:
            total_matches = int(total_info[0])
        except Exception as e:
            self.log('Total Match Error {}'.format(traceback.format_exc(e)))
            total_matches = 0

        return total_matches

    def _scrape_next_results_page_link(self, response):
        self.current_page += 1

        if self.current_page >= self.num_pages:
            return

        start_number = self.count_per_page * self.current_page
        total_matches = self._scrape_total_matches(response)

        if start_number > total_matches:
            return

        tier_id = response.xpath("//input[@id='tierId']/@value").extract()
        if tier_id:
            tier_id = tier_id[0].strip()

            return self.CATEGORIES_URL.format(
                tier_id=tier_id,
                rows=self.count_per_page,
                start=start_number
            )
