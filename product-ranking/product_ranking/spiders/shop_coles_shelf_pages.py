from __future__ import division, absolute_import, unicode_literals

import re
from urlparse import urlparse

from .shop_coles import ShopColesProductsSpider
from scrapy.http import Request
from scrapy.log import WARNING


class ShopColesShelfSpider(ShopColesProductsSpider):
    name = 'shop_coles_shelf_urls_products'
    allowed_domains = ["shop.coles.com.au"]

    PRODUCTS_URL = 'https://shop.coles.com.au/online/a-national/{shelf_param}?tabType=everything' \
                   '&tabId=everything&personaliseSort=false&orderBy=20601_6&errorView=AjaxActionErrorResponse' \
                   '&requesttype=ajax&beginIndex={begin_index}'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))

        super(ShopColesShelfSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        path = urlparse(self.product_url).path
        shelf_param = re.search(r'browse/(.*)', path)
        if shelf_param:
            shelf_param = shelf_param.group(1)
            yield Request(self.PRODUCTS_URL.format(shelf_param=shelf_param, begin_index=0),
                          meta={'search_term': '', 'remaining': self.quantity,
                                'shelf_param': shelf_param})
        else:
            self.log('Error while parsing the shelf param', WARNING)

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return

        totals = self._scrape_total_matches(response)
        page_size = self._scrape_results_per_page(response)
        begin_index = self.current_page * page_size

        if begin_index >= totals:
            return None

        self.current_page += 1
        shelf_param = response.meta.get('shelf_param')
        next_url = self.PRODUCTS_URL.format(shelf_param=shelf_param, begin_index=begin_index)

        return Request(
            next_url,
            meta=response.meta
        )
