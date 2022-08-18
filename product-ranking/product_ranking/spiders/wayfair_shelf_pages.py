# -*- coding: utf-8 -*-

from .wayfair import WayfairProductSpider
from scrapy import Request
from product_ranking.items import SiteProductItem
import re
import urlparse


class WayfairShelfPagesSpider(WayfairProductSpider):
    name = 'wayfair_shelf_urls_products'
    allowed_domains = ["wayfair.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(WayfairShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity}
                      )

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        current_page = response.meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return
        if current_page * 48 > self._scrape_total_matches(response):
            return
        current_page = current_page + 1
        meta['current_page'] = current_page
        url = self.product_url + "?curpage={}".format(current_page)
        return Request(
            url,
            meta=meta,
            callback=self.solve_recaptcha
        )
