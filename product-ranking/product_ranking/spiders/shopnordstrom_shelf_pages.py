# -*- coding: utf-8 -*-

from .shopnordstrom import ShopNordstromProductsSpider
from scrapy.http import Request


class ShopNordstromShelfPagesSpider(ShopNordstromProductsSpider):
    name = 'shopnordstrom_shelf_urls_products'

    CATEGORIES_URL = "{}&page={}&top={}"

    results_per_page = 72

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(ShopNordstromShelfPagesSpider, self).__init__(*args, **kwargs)
        self.prod_url = self.product_url.replace(self.allowed_domains[0],
                                                'shop.nordstrom.com/api')

    def start_requests(self):
        products_url = self.CATEGORIES_URL.format(self.prod_url,
                                                  self.current_page,
                                                  self.results_per_page)

        yield Request(url=products_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      )

    def _scrape_next_results_page_link(self, response):
        if self.results_per_page * self.current_page >= self._scrape_total_matches(response):
            return

        if self.current_page >= self.num_pages:
            return
        self.current_page += 1

        return self.CATEGORIES_URL.format(self.prod_url,
                                          self.current_page,
                                          self.results_per_page)
