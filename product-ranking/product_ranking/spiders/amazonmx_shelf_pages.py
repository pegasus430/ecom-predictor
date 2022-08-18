# ~~coding=utf-8~~
from __future__ import division, absolute_import, unicode_literals

from scrapy.http import Request
from .amazonmx import AmazonProductsSpider


class AmazonMXShelfPagesSpider(AmazonProductsSpider):
    name = 'amazonmx_shelf_urls_products'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        self.num_pages = min(10, self.num_pages)
        super(AmazonMXShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}

    def start_requests(self):
        yield Request(
            url=self.product_url,
            meta=self._setup_meta_compatibility()
        )

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return

        self.current_page += 1

        return super(AmazonMXShelfPagesSpider, self)._scrape_next_results_page_link(response)
