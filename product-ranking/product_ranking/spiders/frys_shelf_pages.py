from __future__ import division, absolute_import, unicode_literals

from product_ranking.spiders.frys import FrysProductsSpider
from scrapy.http import Request


class FrysShelfPagesSpider(FrysProductsSpider):
    name = 'frys_shelf_urls_products'
    allowed_domains = ["frys.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(FrysShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        return {'remaining': self.quantity, 'search_term': ''}

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta=self._setup_meta_compatibility())

    def _scrape_next_results_page_link(self, response):
        if self.current_page < self.num_pages:
            return super(FrysShelfPagesSpider, self)._scrape_next_results_page_link(response)
