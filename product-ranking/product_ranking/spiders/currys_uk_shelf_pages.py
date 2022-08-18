# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

from .currys_uk import CurrysUkProductsSpider
from scrapy.http import Request

from product_ranking.items import SiteProductItem


class CurrysUkShelfPagesSpider(CurrysUkProductsSpider):
    name = 'currys_uk_shelf_urls_products'
    allowed_domains = ["currys.co.uk"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(CurrysUkShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}.copy()

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta=self._setup_meta_compatibility())

    def _scrape_product_links(self, response):
        links = response.xpath(
                '//div[@data-component="product-list-view"]'\
                '//header[@class="productTitle"]/a/@href'
            ).extract()
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if self.current_page < self.num_pages:
            self.current_page += 1

            return super(CurrysUkShelfPagesSpider, self)._scrape_next_results_page_link(response)
