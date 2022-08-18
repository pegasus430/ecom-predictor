# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

from scrapy.log import DEBUG
from .johnlewis import JohnlewisProductsSpider
from scrapy.http import Request


class JohnlewisShelfPagesSpider(JohnlewisProductsSpider):
    name = 'johnlewis_shelf_urls_products'
    allowed_domains = ["www.johnlewis.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(JohnlewisShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}.copy()

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta=self._setup_meta_compatibility())

    def _scrape_total_matches(self, response):
        total = response.xpath(
            './/*[@class="search-header-text"]/h1/text()').re('\((\d+)\)')
        try:
            total = int(total[0]) if total else 0
        except Exception as e:
            self.log("Exception converting total_matches to int: {}".format(e), DEBUG)
            total = 0
        finally:
            return total

    def _scrape_next_results_page_link(self, response):
        if self.current_page < self.num_pages:
            next = response.xpath('.//li[@class="next"]/a[not(@class="disabled")]/@href').extract()
            self.current_page += 1
            if next:
                return next[0]

