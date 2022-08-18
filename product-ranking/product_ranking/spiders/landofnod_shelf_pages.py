# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

from .landofnod import LandOfNodProductsSpider
from scrapy.http import Request


class LandOfNodShelfPagesSpider(LandOfNodProductsSpider):
    name = 'landofnod_shelf_urls_products'
    allowed_domains = ["www.landofnod.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(LandOfNodShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}.copy()

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta=self._setup_meta_compatibility())

