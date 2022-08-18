# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import re
from .crutchfield import CrutchfieldProductsSpider
from scrapy.http import Request
from scrapy.log import ERROR


class CrutchfieldShelfPagesSpider(CrutchfieldProductsSpider):
    name = 'crutchfield_shelf_urls_products'
    SHELF_AJAX_URL = "https://www.crutchfield.com/handlers/product/group/list.ashx?" \
                     "g={category_id}&pg={page_number}&start={start_position}"

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        self.category_id = None
        super(CrutchfieldShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _get_category_id(self):
        category_id = re.findall(r'(?<=g_)\d+', self.product_url)
        if category_id:
            return category_id[0]

    def start_requests(self):
        category_id = self._get_category_id()
        if category_id:
            self.category_id = category_id
            url = self.SHELF_AJAX_URL.format(category_id=category_id, page_number=1, start_position=1)
            yield Request(url=url,
                          meta={'search_term': "", 'remaining': self.quantity},
                          dont_filter=True)
        else:
            self.log("Can not find category ID", ERROR)

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        current_page = meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return
        total_matches = meta.get('total_matches')
        if current_page * 20 > total_matches:
            return
        start_position = current_page * 20 + 1
        current_page += 1
        url = self.SHELF_AJAX_URL.format(category_id=self.category_id, page_number=current_page, start_position=start_position)
        meta['current_page'] = current_page
        return Request(
            url,
            meta=meta
        )