from __future__ import absolute_import, division, unicode_literals

from scrapy.http import Request
from .surlatable import SurlatableProductsSpider


class SurlatableShelfPagesSpider(SurlatableProductsSpider):
    name = 'surlatable_shelf_urls_products'
    allowed_domains = ["www.surlatable.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(SurlatableShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(
            url=self.product_url,
            meta={'remaining': self.quantity, 'search_term': ''},
            dont_filter=True
        )

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return

        self.current_page += 1
        return super(SurlatableShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)