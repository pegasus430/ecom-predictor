# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

from scrapy.http import Request
from product_ranking.items import SiteProductItem
from scrapy import Selector
import json
import re
import traceback

from .poundland_co_uk import PoundlandCoUkProductsSpider
from product_ranking.utils import valid_url


class PoundLandShelfPagesSpider(PoundlandCoUkProductsSpider):
    name = 'poundland_shelf_urls_products'
    PRODUCTS_URL = "http://www.poundland.co.uk/ampersand-ajaxproductloader" \
                   "/index/index/?id={id}&page={page_id}&columnCount=4"

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))
        self.category_id = None

        super(PoundLandShelfPagesSpider, self).__init__(*args, **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}.copy()

    def start_requests(self):
        if self.product_url:
            yield Request(url=valid_url(self.product_url),
                          callback=self._start_requests)

    def _start_requests(self, response):
        try:
            category_temp = re.search('category_id: (.*?)}', response.body_as_unicode(), re.DOTALL).group(1)
            self.category_id = re.search('category_id: (.*?)\n', category_temp).group(1).replace("'", "")
            yield Request(url=self.PRODUCTS_URL.format(id=self.category_id, page_id=self.current_page),
                          meta=self._setup_meta_compatibility())
        except:
            self.log("Found no category id {}".format(traceback.format_exc()))

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        try:
            data = json.loads(response.body_as_unicode())
            content = data['content']
            items = Selector(text=content).xpath('//ul[contains(@class, "products-grid")]'
                                                 '/li/a[contains(@class, "product-image")]/@href').extract()
            if items:
                for item in items:
                    res_item = SiteProductItem()
                    yield item, res_item
        except:
            self.log("Found no product links {}".format(traceback.format_exc()))

    def _scrape_next_results_page_link(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            next_page_load = data['nextPageToLoad']
            if next_page_load == 0:
                return

            self.current_page += 1

            next_page = self.PRODUCTS_URL.format(id=self.category_id, page_id=self.current_page)
            return next_page
        except:
            self.log("Found no next link {}".format(traceback.format_exc()))
            return None

    def parse_product(self, response):
        return super(PoundLandShelfPagesSpider, self).parse_product(response)