from __future__ import absolute_import, division, unicode_literals

from scrapy.http import Request

from .hayneedle import HayneedleProductSpider


class HayneedleShelfPagesSpider(HayneedleProductSpider):
    name = 'hayneedle_shelf_urls_products'
    allowed_domains = ["www.hayneedle.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(HayneedleShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

        self.product_url = self.product_url.replace('\'', '')

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
        return super(HayneedleShelfPagesSpider, self)._scrape_next_results_page_link(response)

