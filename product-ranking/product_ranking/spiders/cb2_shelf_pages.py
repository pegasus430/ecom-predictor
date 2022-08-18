# -*- coding: utf-8 -*-

from .cb2 import Cb2ProductsSpider
from scrapy.http import Request


class Cb2ShelfPagesSpider(Cb2ProductsSpider):
    name = 'cb2_shelf_urls_products'
    allowed_domains = ["cb2.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(Cb2ShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      callback=self.check_captcha,
                      )

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        return super(Cb2ShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)
