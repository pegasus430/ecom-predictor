# -*- coding: utf-8 -*-

from .supplyworks import SupplyworksProductsSpider
from scrapy.http import Request
from product_ranking.utils import is_empty


class SupplyworksShelfPagesSpider(SupplyworksProductsSpider):
    name = 'supplyworks_shelf_urls_products'
    allowed_domains = ["www.supplyworks.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(SupplyworksShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      callback=self._start_requests
                      )
    def _start_requests(self, response):
        st = response.xpath("//div[contains(@class, 'pure-u-lg-16-24')]//h1/text()").extract()
        if st:
            return Request(url=self.product_url,
                           meta={'search_term': st[0], 'remaining': self.quantity},
                           dont_filter=True
                           )

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return None

        return super(SupplyworksShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)

