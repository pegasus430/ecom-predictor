# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re

from scrapy.http import Request
from .sephora import SephoraProductsSpider


class SephoraShelfPagesSpider(SephoraProductsSpider):
    name = 'sephora_shelf_urls_products'

    CATEGORY_URL = 'https://www.sephora.com/{category_id}?currentPage={current_page}'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', 1))
        super(SephoraShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        category_id = self.product_url.split('/')[-1]
        yield Request(url=self.CATEGORY_URL.format(category_id=category_id, current_page=1),
                      meta={'remaining': self.quantity,
                            'search_term': '',
                            'current_page': 1,
                            'category_id': category_id})

    def _scrape_total_matches(self, response):
        total_matches = re.search('"total_products":(\d+)', response.body, re.DOTALL)
        return int(total_matches.group(1)) if total_matches else None

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        current_page = meta.get('current_page', 1)
        category_id = meta.get('category_id')
        total_matches = meta.get('total_matches', 0)
        if current_page >= self.num_pages or current_page * 60 > total_matches:
            return
        current_page += 1
        meta['current_page'] = current_page
        url = self.CATEGORY_URL.format(category_id=category_id, current_page=current_page)
        return Request(url=url, meta=meta)

    def _get_products(self, response):
        for request in super(SephoraShelfPagesSpider, self)._get_products(response):
            request = request.replace(dont_filter=True)
            yield request
