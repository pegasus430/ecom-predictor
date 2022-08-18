# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback

from .bigbasket import BigbasketProductsSpider
from scrapy.http import Request
from scrapy.log import WARNING
from product_ranking.items import SiteProductItem


class BigbasketShelfPagesSpider(BigbasketProductsSpider):
    name = 'bigbasket_shelf_urls_products'
    allowed_domains = ["www.bigbasket.com"]

    AUTH_URL = "https://www.bigbasket.com/skip_explore/?c=1&l=0&s=0&n=%2F"
    PRODUCTS_URL = "https://www.bigbasket.com/custompage/getsearchdata/?slug={term}&type=deck"
    PAGINATION_URL = "https://www.bigbasket.com/product/get-products/?slug={term}&page={page_num}&listtype=ps"

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(BigbasketShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

        self.user_agent = 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'

    def _setup_meta_compatibility(self):
        return {'remaining': self.quantity, 'search_term': ''}.copy()

    def start_requests(self):
        yield Request(
            self.AUTH_URL,
            callback=self._start_requests
        )

    def _start_requests(self, response):
        if self.product_url:
            yield Request(
                self.product_url,
                meta={'remaining': self.quantity, 'search_term': ''},
                callback=self.get_products
            )

    def get_products(self, response):
        term = re.search("slug = '(.*?)\';", response.body)
        if term:
            term = term.group(1)
            return Request(
                self.PRODUCTS_URL.format(term=term),
                meta={
                    'remaining': self.quantity,
                    'search_term': term
                },
                dont_filter=True
            )
        else:
            self.log('Slug value is None', WARNING)

    def _scrape_total_matches(self, response):
        try:
            self.total_matches = json.loads(response.body)['json_data']['tab_info'][0]['product_info']['p_count']
        except Exception as e:
            self.log("Error while parsing total matches: {}".format(traceback.format_exc(e)))
            self.total_matches = 0

        if not self.total_matches:
            self.total_matches = response.meta.get('total_matches')
        return self.total_matches

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body)
            if 'tab_info' in data:
                products = data.get('tab_info', {}).get('product_map', {}).get('all', {}).get('prods', {})
            else:
                products = data.get('json_data', {}).get('tab_info', {})[0].get('product_info', {}).get('products', {})
            links = []
            for product in products:
                if 'media/uploads/p/mm' in product.get('p_img_url'):
                    links.append(product.get('p_img_url').replace('media/uploads/p/mm', 'pd').replace('.jpg', ''))
                else:
                    links.append(product.get('p_img_url').replace('media/uploads/p/s', 'pd').replace('.jpg', ''))
            self.product_links = links

            for item_url in links:
                yield item_url, SiteProductItem()

        except Exception as e:
            self.log("Error while parsing json: {}".format(traceback.format_exc(e)))
            self.product_links = []

    def _scrape_next_results_page_link(self, response):
        if self.current_page > self.num_pages:
            return None

        results_per_page = response.meta.get('scraped_results_per_page')
        if self.current_page * results_per_page >= self.total_matches:
            return

        self.current_page += 1
        term = response.meta.get('search_term')
        return Request(
            self.PAGINATION_URL.format(term=term, page_num=self.current_page),
            meta={
                'remaining': self.quantity,
                'search_term': term,
                'total_matches': self.total_matches
            },
            dont_filter=True
        )
