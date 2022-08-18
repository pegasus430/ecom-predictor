# -*- coding: utf-8 -*-

from .neweggca import NeweggcaProductsSpider
from scrapy.http import Request


class NeweggCAShelfPagesSpider(NeweggcaProductsSpider):
    name = 'neweggca_shelf_urls_products'
    allowed_domains = ["www.newegg.ca", "newegg.ca"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(NeweggCAShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      )

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        return super(NeweggCAShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)
