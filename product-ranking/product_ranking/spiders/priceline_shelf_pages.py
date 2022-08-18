# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

from .priceline import PriceLineProductsSpider
from scrapy.http import Request
from scrapy.log import INFO

from product_ranking.items import SiteProductItem
from product_ranking.utils import valid_url


class PriceLineShelfPagesSpider(PriceLineProductsSpider):
    name = 'priceline_shelf_urls_products'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(PriceLineShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      meta={'search_term': '', 'remaining': self.quantity})

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//ul[contains(@class, "products-grid")]'
                               '/li/div[contains(@class, "product-image")]'
                               '/a/@href').extract()

        if items:
            for item in items:
                res_item = SiteProductItem()
                yield item, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return

        self.current_page += 1

        return super(PriceLineShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)