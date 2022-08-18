# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import urlparse

from scrapy.log import INFO
from scrapy.conf import settings

from product_ranking.items import (SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty


class PriceLineProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'priceline_products'
    allowed_domains = ["www.priceline.com.au", "priceline.com.au"]

    SEARCH_URL = "https://www.priceline.com.au/search/?q={search_term}"

    def __init__(self, *args, **kwargs):
        super(PriceLineProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

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
        title = is_empty(response.xpath('//div[@class="product-name"]'
                                        '//span[@itemprop="name"]/text()').extract())
        return title

    @staticmethod
    def _parse_brand(response):
        brand = is_empty(response.xpath('//span[@itemprop="brand"]/text()').extract())
        return brand

    @staticmethod
    def _parse_sku(response):
        sku = is_empty(response.xpath('//span[@itemprop="sku"]/text()').extract())
        return sku

    @staticmethod
    def _parse_out_of_stock(response):
        out_of_stock = response.xpath('//meta[@property="product:availability"]/@content').extract()
        if out_of_stock:
            out_of_stock = out_of_stock[0].lower()
        if out_of_stock == 'in stock':
            return False
        return True

    @staticmethod
    def _parse_categories(response):
        category_list = []
        category_temp = response.url.split('https://www.priceline.com.au/')[1]
        categories = category_temp.split('/')[:-1]
        for category in categories:
            category = category.replace('-', ' ').replace(' and', ' &')
            category_list.append(category)
        return category_list

    @staticmethod
    def _parse_price(response):
        currency = "AUD"
        price = response.xpath('//span[@itemprop="price"]/text()').re(FLOATING_POINT_RGEX)
        if price:
            return Price(price=float(price[0]), priceCurrency=currency)

    @staticmethod
    def _parse_image_url(response):
        image_url = is_empty(response.xpath('//div[contains(@class, "product-image")]'
                                            '/a/img[@itemprop="image"]/@src').extract())
        return image_url

    @staticmethod
    def _parse_description(response):
        desc = is_empty(response.xpath('//div[contains(@class, "product-main-info")]'
                                       '/div[@itemprop="description"]/text()').extract())
        return desc

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        totals = response.xpath('//div[contains(@class, "result-view")]'
                                '/h3/text()').extract()
        if totals:
            totals = re.search('found (\d+)', totals[1])
            return int(totals.group(1)) if totals else 0

    def _scrape_results_per_page(self, response):
        item_count = is_empty(response.xpath('//div[contains(@class, "limiter")]'
                                             '/select/option[contains(@selected, "selected")]'
                                             '/text()').extract())
        if item_count:
            item_count = re.findall('(\d+)', item_count)
            return item_count[0] if item_count else 0

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//ul[contains(@class, "products-grid")]'
                               '/li/div[contains(@class, "product-image")]'
                               '/a/@href').extract()

        if items:
            for item in items:
                res_item = SiteProductItem()
                yield item, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath('//div[@class="pages"]/ol/li'
                                   '/a[@title="Next"]/@href').extract()
        if next_page:
            return urlparse.urljoin(response.url, next_page[0])