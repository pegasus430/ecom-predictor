# -*- coding: utf-8 -*-

import re

from .flipkart import FlipkartProductsSpider
from scrapy import Request


class FlipkartShelfPagesSpider(FlipkartProductsSpider):
    name = 'flipkart_shelf_urls_products'
    allowed_domains = ["www.flipkart.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(FlipkartShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      )

    def _scrape_total_matches(self, response):
        total_info = response.xpath("//div[@class='C5rIv_']//span/text()").extract()
        total_match = 0

        if total_info:
            total_match = re.search('of(.*?)products', total_info[0])
        if total_match:
            total_match = int(total_match.group(1).replace(',', ''))
        return total_match

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return None

        self.current_page += 1
        return super(FlipkartShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)