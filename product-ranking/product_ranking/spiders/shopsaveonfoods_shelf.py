# -*- coding: utf-8 -*-

import re

from .shopsaveonfoods import ShopsaveonfoodsProductsSpider
from scrapy.http import Request
from scrapy.log import WARNING


class ShopsaveonfoodsShelfPagesSpider(ShopsaveonfoodsProductsSpider):
    name = 'shopsaveonfoods_shelf_urls_products'
    allowed_domains = ["shop.saveonfoods.com"]

    SHELF_PRODUCT_URL = "https://shop.saveonfoods.com/api/product/v7/products/category/{category_id}/store/{store_id}" \
                        "?sort=Brand&skip={offset}&take=20&userId={user_id}"

    SPECIAL_SHELF_PRODUCT_URL = "https://shop.saveonfoods.com/api/product/v7/products/category/{category_id}/store/{store_id}" \
                        "?sort=Brand&skip={offset}&take=20&userId={user_id}&fq=specials%3Aall"

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(ShopsaveonfoodsShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests_with_csrf(self, response):
        csrf = self.get_csrf(response)
        user_id = self.get_user_id(response)

        headers = {
            "Accept": "application/vnd.mywebgrocer.grocery-list+json",
            "Authorization": csrf,
            "X-Requested-With": "XMLHttpRequest",
        }

        try:
            category_id = re.search('category/(.*?)\/', self.product_url).group(1)
            c_id = category_id.split(',')[-1]
            c_special_id = category_id.split(',')[0]
            if self.store and csrf and category_id and user_id:
                if c_special_id == '000':
                    prod_url = self.SPECIAL_SHELF_PRODUCT_URL.format(offset=0,
                                                                     store_id=self.store,
                                                                     category_id=c_id,
                                                                     user_id=user_id)
                else:
                    prod_url = self.SHELF_PRODUCT_URL.format(offset=0,
                                                             store_id=self.store,
                                                             category_id=c_id,
                                                             user_id=user_id)
        except:
            self.log("Error while parsing json data {}".format(traceback.format_exc()))

        return Request(
                    url=prod_url,
                    meta={'search_term': '',
                          'remaining': self.quantity,
                          'csrf': csrf,
                          'user_id': user_id,
                          'headers': headers,
                          'store_id': self.store,
                          'category_id': category_id,
                          'current_page': 1
                          },
                    dont_filter=True,
                    headers=headers
                )

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        current_page = meta.get('current_page')

        if current_page >= self.num_pages:
            return None
        current_page += 1

        user_id = meta.get('user_id')
        store = meta.get('store_id')
        category_id = meta.get('category_id')

        headers = meta.get('headers')
        headers['Accept'] = "application/vnd.mywebgrocer.grocery-list+json"
        headers['Accept-Encoding'] = "gzip, deflate, br"
        headers['Connection'] = "keep-alive"
        headers['X-Requested-With'] = "XMLHttpRequest"

        meta['headers'] = headers
        meta['current_page'] = current_page

        totals = self._scrape_total_matches(response)

        offset = current_page * self.product_per_page
        if totals and offset >= totals:
            return

        return Request(
            url=self.SHELF_PRODUCT_URL.format(
                offset=offset, user_id=user_id,
                store_id=store, category_id=category_id,
            ),
            meta=meta,
            dont_filter=True,
            headers=headers
        )