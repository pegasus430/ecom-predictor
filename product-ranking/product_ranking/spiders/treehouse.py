# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import string
from urlparse import urljoin
import re
import json
import traceback

from scrapy.http import Request

from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator


class TreeHouseProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'treehouse_products'
    allowed_domains = ['tree.house']

    CURRENCY = 'USD'

    BASE_URL = 'https://tree.house'

    SEARCH_URL = 'https://hsdij4qdcr-dsn.algolia.net/1/indexes/content/query?x-algolia-agent=Algolia%20for%20vanilla' \
                 '%20JavaScript%203.20.2&x-algolia-application-id=HSDIJ4QDCR&x-algolia-api-key' \
                 '=bdce7f43fd6b714f30cc230ff19257f1'

    results_per_page = 20

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
    }

    handle_httpstatus_list = [400]

    def start_requests(self):
        if not self.searchterms:
            for request in super(TreeHouseProductsSpider, self).start_requests():
                yield request

        for st in self.searchterms:
            query_string = "query={}".format(st)
            payload = {
                "params": query_string
            }

            yield Request(
                self.SEARCH_URL,
                method='POST',
                body=json.dumps(payload),
                headers=self.headers,
                meta={'search_term': st, 'remaining': self.quantity},
            )

    def parse_product(self, response):
        product = response.meta['product']

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse department
        department = self._parse_department(response)
        cond_set_value(product, 'department', department)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse stock status
        out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', out_of_stock)

        # Parse stock status
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        return product

    @staticmethod
    def _parse_brand(response):
        brand = re.search('"brand":"(.*?)",', response.body)
        if brand:
            return brand.group(1)

    @staticmethod
    def _parse_title(response):
        title = response.xpath(
            '//*[@itemprop="name"]'
        ).extract()
        if title:
            return title[0]

    def _parse_price(self, response):
        price = response.xpath(
            '//*[@itemprop="price"]/@content'
        ).re(FLOATING_POINT_RGEX)
        if price:
            return Price(
                price=float(price[0].replace(',', '')),
                priceCurrency=self.CURRENCY
            )

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath(
            '//meta[@itemprop="image"]/@content'
        ).extract()
        if image_url:
            return urljoin(response.url, image_url[0])

    @staticmethod
    def _parse_department(response):
        department = response.xpath(
            '//div[@class="menu"]/div[contains(@class, "label")]/a/text() | '
            '//div[@class="menu"]/div[contains(@class, "label")]/text()'
        ).extract()
        return department[0] if department else None

    @staticmethod
    def _parse_description(response):
        description = response.xpath(
            '//*[@itemprop="description"]//text()'
        ).extract()
        return ''.join(description) if description else None

    @staticmethod
    def _parse_is_out_of_stock(response):
        in_stock = response.xpath('//*[@itemprop="availability"]/@href').extract()
        if in_stock:
            return in_stock[0] != 'http://schema.org/InStock'
        return True

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = re.search('productId":(.*?),', response.body, re.DOTALL)
        if reseller_id:
            return reseller_id.group(1)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_product_links(self, response):
        try:
            products = json.loads(response.body).get('hits', [])

            for product in products:
                link = product.get('link')
                if link:
                    yield link, SiteProductItem()

        except:
            self.log('Product Links Error: {}'.format(traceback.format_exc()))

    def _scrape_total_matches(self, response):
        # Impossible to implement field
        return None

    def _scrape_next_results_page_link(self, response):
        return None
