# -*- coding: utf-8 -*-#

from product_ranking.utils import valid_url
from .staplesadvantage import StaplesadvantageProductsSpider
from scrapy import Request
import math


class StaplesadvantageShelfPagesSpider(StaplesadvantageProductsSpider):
    name = 'staplesadvantage_shelf_urls_products'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(StaplesadvantageShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      meta={'remaining': self.quantity, 'search_term': ''})

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return

        total_matches = self._scrape_total_matches(response)
        results_per_page = self._scrape_results_per_page(response)
        if not results_per_page:
            results_per_page = 25
        if (total_matches and results_per_page and
                    self.current_page < math.ceil(total_matches / float(results_per_page))):
            self.current_page += 1
            shelf_url = self.product_url
            if '&pg=' in self.product_url:
                shelf_url = self.product_url.split('&pg=')[0]
            next_link = shelf_url + '&pg={}'.format(self.current_page)
            return next_link
