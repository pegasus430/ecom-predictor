# -*- coding: utf-8 -*-

from .anthropologie import AnthropologieProductsSpider
from scrapy.http import Request

class AnthropologieShelfPagesSpider(AnthropologieProductsSpider):
    name = 'anthropologie_shelf_urls_products'
    allowed_domains = ["www.anthropologie.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(AnthropologieShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      )

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return None
        next = response.xpath("//a[@aria-label='next page']/@href").extract()
        self.current_page += 1
        if next:
            return next[0]
