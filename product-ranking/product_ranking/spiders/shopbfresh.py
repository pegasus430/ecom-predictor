# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import json
import traceback

import re
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import (SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider
from scrapy import Request
from scrapy.conf import settings
from scrapy.log import INFO


class ShopBfreshProductsSpider(BaseProductsSpider):
    name = 'shopbfresh_products'
    allowed_domains = ["https://shop.bfresh.com"]

    SEARCH_URL = "https://shop.bfresh.com/en/?q={search_term}"

    QUERY_URL = "https://shop.bfresh.com/api/query.json"

    PRODUCT_URL = "https://shop.bfresh.com/en/{sku}/{slug}"

    HEADERS = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
    }

    formdata = \
        {
            "meta": {},
            "request": [
                {
                    "args": {
                        "store_id": "00034100",
                        "query": None,
                        "facets": [],
                        "extended": True
                    },
                    "v": "0.1",
                    "type": "store.search_web",
                    "id": "search",
                    "offset": 1,
                    "join": [
                        {
                            "apply_as": "facets_base",
                            "on": ["query", "query"],
                            "request": {
                                "v": "0.1",
                                "type": "store.facets",
                                "args": {
                                    "store_id": "$request.[-2].args.store_id",
                                    "query": "$request.[-2].args.query"
                                }
                            }
                        }
                    ]
                }
            ]
        }

    single_product_formdata = \
        {
            "meta": {},
            "request": [
                {
                    "args": {
                        "store_id": "00034100",
                        "eans": None
                    },
                    "v": "0.1",
                    "type": "product.details",
                    "id": None
                }
            ]
        }

    def __init__(self, *args, **kwargs):
        super(ShopBfreshProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        for st in self.searchterms:
            formdata = self.formdata.copy()
            formdata['request'][0]['args']['query'] = st
            yield Request(
                self.QUERY_URL,
                method='POST',
                headers=self.HEADERS,
                body=json.dumps(formdata),
                meta={'search_term': st, 'remaining': self.quantity, 'formdata': formdata},
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''

            product_id = self._extract_id_from_url(self.product_url)
            if product_id:
                formdata = self.single_product_formdata.copy()
                formdata['request'][0]['args']['eans'] = [product_id]
                formdata['request'][0]['id'] = "product_{}_full".format(product_id)
                yield Request(
                    self.QUERY_URL,
                    method='POST',
                    headers=self.HEADERS,
                    callback=self.parse_product,
                    body=json.dumps(formdata),
                    meta={'product': prod}
                )

        if self.products_url:
            urls = self.products_url.split('||||')
            for url in urls:
                prod = SiteProductItem()
                prod['url'] = url
                prod['search_term'] = ''

                product_id = self._extract_id_from_url(url)
                if product_id:
                    formdata = self.single_product_formdata.copy()
                    formdata['request'][0]['args']['eans'] = [product_id]
                    formdata['request'][0]['id'] = "product_{}_full".format(product_id)
                    yield Request(
                        self.QUERY_URL,
                        method='POST',
                        headers=self.HEADERS,
                        callback=self.parse_product,
                        body=json.dumps(formdata),
                        meta={'product': prod}
                    )

    @staticmethod
    def _extract_id_from_url(url):
        product_id = re.findall(r'(?<=/)(.*?)(?=/.+\Z)', url)
        return product_id[-1] if product_id else None

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        try:
            body = json.loads(response.body_as_unicode())
            item = body.get('responses')[0].get('data').get('items')[0]
            return self._fill_item(item, SiteProductItem())
        except:
            self.log("Unable to load json response, product parsing failed: {}".format(traceback.format_exc()))

    def _scrape_total_matches(self, response):
        try:
            body = json.loads(response.body_as_unicode())
            totals = body.get('responses')[0].get('data').get('items')[0].get('total')
            return int(totals)
        except:
            self.log("Unable to count total matches, search failed: {}".format(traceback.format_exc()))

    def _scrape_product_links(self, response):
        try:
            body = json.loads(response.body_as_unicode())
            items = body.get('responses')[0].get('data').get('items')[0].get('items')
        except:
            self.log("Unable to get json response, search failed: {}".format(traceback.format_exc()))
            return

        if items:
            for item in items:
                filled_item = self._fill_item(item, SiteProductItem())
                yield None, filled_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _fill_item(self, item, product):

        product['title'] = item.get('name')

        brand = item.get('extended_info', {}).get('tm')
        if not brand:
            brand = guess_brand_from_first_words(product['title'])
        product['brand'] = brand

        product['is_out_of_stock'] = not (item.get('available'))

        image_url = item.get('main_image', {}).get('s1350x1350')
        if not image_url:
            image_url = item.get('main_image', {}).get('s350x350')
        product['image_url'] = image_url

        product['description'] = None

        categories = item.get('path')
        product['categories'] = categories
        product['department'] = categories[0] if categories else None

        try:
            price = float(item.get('price')) / 100
        except:
            price = None

        product['price'] = Price(price=price, priceCurrency='USD') if price else None

        product['reseller_id'] = item.get('ean')

        product['sku'] = item.get('sku')

        product['url'] = self.PRODUCT_URL.format(sku=item.get('ean'), slug=item.get('slug'))

        return product

    def _scrape_next_results_page_link(self, response):
        try:
            body = json.loads(response.body_as_unicode())

            total_pages = body.get('responses')[0].get('data').get('items')[0].get('num_pages')
            formdata = response.meta.get('formdata')
            page_num = formdata['request'][0]['offset']
            if page_num < total_pages:
                formdata['request'][0]['offset'] += 1
                response.meta['formdata'] = formdata
                return Request(
                    self.QUERY_URL,
                    method='POST',
                    headers=self.HEADERS,
                    body=json.dumps(formdata),
                    meta=response.meta,
                    dont_filter=True
                )
        except:
            self.log("Unable to get next page link: {}".format(traceback.format_exc()))
