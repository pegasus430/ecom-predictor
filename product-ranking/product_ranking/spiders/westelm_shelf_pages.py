from __future__ import division, absolute_import, unicode_literals

from .westelm import WestelmProductsSpider
from scrapy.http import Request


class WestelmShelfPagesSpider(WestelmProductsSpider):
    name = 'westelm_shelf_urls_products'
    allowed_domains = ["www.westelm.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(WestelmShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}.copy()

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta=self._setup_meta_compatibility())

    def _scrape_next_results_page_link(self, response):
        if self.current_page < self.num_pages:
            self.current_page += 1

            return super(WestelmShelfPagesSpider, self)._scrape_next_results_page_link(response)

    def _scrape_total_matches(self, response):
        return None
