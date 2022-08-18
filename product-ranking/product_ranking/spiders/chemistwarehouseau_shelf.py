# -*- coding: utf-8 -*-

from .chemistwarehouseau import ChemistwarehouseauProductsSpider
from scrapy.http import Request


class ChemistwarehouseauShelfPagesSpider(ChemistwarehouseauProductsSpider):
    name = 'chemistwarehouseau_shelf_urls_products'
    allowed_domains = ["www.chemistwarehouse.com.au"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(ChemistwarehouseauShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      )

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        return super(ChemistwarehouseauShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)
