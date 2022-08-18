# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import json
import urlparse

from scrapy.http import Request
from scrapy.log import INFO
from scrapy.conf import settings
from product_ranking.items import SiteProductItem
from product_ranking.utils import valid_url

from .sanalmarket import SanalMarketProductsSpider


class SanalMarketShelfPagesSpider(SanalMarketProductsSpider):
    name = 'sanalmarket_shelf_urls_products'
    CATEGORY_API_URL = "https://www.sanalmarket.com.tr/kweb/getProductList.do?shopCategoryId={}"

    def __init__(self, *args, **kwargs):
        self.current_page = 1
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', 1))
        super(SanalMarketShelfPagesSpider, self).__init__(*args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      callback=self._start_requests,
                      meta={'remaining': self.quantity,
                            'search_term': ''})

    def _start_requests(self, response):
        shop_category_id = re.search('shopCategoryId=(\d+)', response.body)
        if shop_category_id:
            shop_category_id = shop_category_id.group(1)
            return Request(url=self.CATEGORY_API_URL.format(shop_category_id),
                           meta=response.meta)

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            items = data.get('aaData', [])
            if items:
                for item in items:
                    res_item = SiteProductItem()
                    link = item.get('uri')
                    link = urlparse.urljoin(response.url, link)
                    yield link, res_item
        except:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return

        self.current_page += 1
        return super(SanalMarketShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)