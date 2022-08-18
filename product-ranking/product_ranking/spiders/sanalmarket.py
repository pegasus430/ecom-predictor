# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import string
import urlparse
import traceback
import json

from scrapy import Request
from scrapy.conf import settings

from product_ranking.items import (SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator


class SanalMarketProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'sanalmarket_products'
    allowed_domains = ["sanalmarket.com.tr"]

    SEARCH_URL = "https://www.sanalmarket.com.tr/kweb/searchInShop.do?btnUstArama.x=0&btnUstArama.y=0"\
                 "&searchKeyword={search_term}&kangurumMigrosSearch=true&shopId=1"

    SEARCH_DATA_URL = "https://www.sanalmarket.com.tr/kweb/getFastPurchaseProductList.do?item=0"

    def __init__(self, *args, **kwargs):
        super(SanalMarketProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        for request in super(SanalMarketProductsSpider, self).start_requests():
            if not request.meta.get('search_data', False) and not self.product_url:
                request = request.replace(callback=self._get_search_data)
            yield request

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku, conv=string.strip)

        # Parse out of stock
        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//*[@itemprop="name"]/text()').extract()
        if title:
            return title[0]

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//input[@name="brand"]/@value').extract()
        if brand:
            return brand[0]

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath('//input[@name="sku"]/@value').extract()
        if sku:
            return sku[0]

    @staticmethod
    def _parse_out_of_stock(response):
        out_of_stock = response.xpath('//input[contains(@name, "isOnStocks")]/@value').extract()
        if out_of_stock and out_of_stock[0] == 'true':
            return False
        return True

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//ul[@class="titleNavList"]/li/a[@itemprop="url"]'
                                    '/span[@itemprop="title"]/text()').extract()
        categories = [category.replace('>', '').strip() for category in categories]
        return categories

    def _parse_price(self, response):
        currency = "TRY"
        price = response.xpath('//*[@name="price"]/@value').extract()
        if price:
            try:
                return Price(price=float(price[0]), priceCurrency=currency)
            except:
                self.log("Price Error {}".format(traceback.format_exc()))

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath('//input[@name="productImage"]/@value').extract()
        if image_url:
            return image_url[0]

    @staticmethod
    def _parse_description(response):
        desc = response.xpath('//div[@itemprop="description"]//text()').extract()
        return "".join(desc)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            items = data.get('aaData', [])
            totals = len(items)
            return totals
        except:
            self.log("Found no total matches".format(traceback.format_exc()))

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        try:
            data = json.loads(response.body_as_unicode())
            items = data.get('aaData', [])
            for item in items:
                res_item = SiteProductItem()
                link = item.get('uri')
                link = urlparse.urljoin(response.url, link)
                yield link, res_item
        except:
            self.log("Found no product links".format(traceback.format_exc()))

    def _get_search_data(self, response):
        meta = response.meta.copy()
        meta['search_data'] = True
        return Request(
            self.SEARCH_DATA_URL,
            meta=meta
        )

    def _scrape_next_results_page_link(self, response):
        return
