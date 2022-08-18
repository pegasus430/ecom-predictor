# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import json
import re
import string
import urlparse

from scrapy.log import DEBUG, INFO

from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import (BaseProductsSpider, cond_set_value,
                                     FLOATING_POINT_RGEX)
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty


class IkeaProductsSpider(BaseValidator, BaseProductsSpider):

    name = 'ikea_products'
    allowed_domains = ["www.ikea.com", "ikea.com"]

    SEARCH_URL = "http://www.ikea.com/us/en/search/?query={search_term}"

    items_per_page = 25
    start_links = 'http://www.ikea.com/us/en/'

    def __init__(self, *args, **kwargs):
        super(IkeaProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        self.current_page = 1

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
        cond_set_value(product, 'brand', brand)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse special pricing
        special_pricing = self._parse_special_pricing(response)
        cond_set_value(product, 'special_pricing', special_pricing, conv=bool)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        # Parse stock status
        is_out_of_stock = self._parse_stock_status(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # reseller_id
        cond_set_value(product, 'reseller_id', sku)

        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        return product

    def _parse_variants(self, response):
        try:
            js = json.loads(
                re.search(
                    'jProductData\s*=\s*({.*})',
                    response.body_as_unicode()
                ).group(1)
            )
        except:
            return None

        variants = []
        items = js.get('product', {}).get('items', [])
        for item in items:
            price = item.get('prices', {}).get('normal', {}) \
                .get('priceNormal', {}).get('value')
            image_url = is_empty(item.get('images', {}).get('zoom', []))
            color = item.get('color')
            if not color:
                color = '/'.join(item.get('validDesign', []))
            variant = {
                'properties': {
                    'sku': item.get('partNumber'),
                    'color': color,
                },
                'price': price,
                'url': urlparse.urljoin(response.url, item.get('url')),
                'image_url': urlparse.urljoin(response.url, image_url),
            }
            variants.append(variant)

        return variants

    @staticmethod
    def _parse_title(response):
        title = is_empty(
            response.xpath(
                '//*[@id="schemaProductName"]/text()'
            ).extract()
        )

        return title

    @staticmethod
    def _parse_brand(response):
        brand = is_empty(response.xpath('//span[@itemprop="brand"]//span/text()').extract())
        return brand

    def _parse_categories(self, response):
        categories_sel = response.xpath('//ul[@id="breadCrumbs"]/li'
                                             '/a/text()').extract()
        categories = [i.strip() for i in categories_sel]
        return categories[1:] if categories else None

    def _parse_price(self, response):
        # default value
        currency = "USD"
        price = is_empty(
            response.xpath(
                '//div[@id="prodPrice"]//span[contains(@class, "packagePrice")]/text()'
            ).re(FLOATING_POINT_RGEX), '0'
        )

        return Price(price=price, priceCurrency=currency)

    def _parse_special_pricing(self, response):
        special_price = is_empty(
            response.xpath(
                '//div[@class="productType"]//span'
            ).extract(), False
        )

        return special_price

    def _parse_image_url(self, response):
        image_url = is_empty(
            response.xpath(
                '//meta[@property="og:image"]/@content'
            ).extract()
        )

        return image_url.replace('S4.JPG', 'S5.JPG') if image_url else None

    def _parse_description(self, response):
        desc = is_empty(
            response.xpath(
                '//*[@id="schemaProductDesc"]/text()'
            ).extract()
        )

        return desc

    def _parse_stock_status(self, response):
        stock_status = is_empty(
            response.xpath(
                '//*[@id="itemBuyable"]/@value'
            ).extract()
        )

        return False if 'true' in stock_status else True

    def _parse_sku(self, response):
        sku = re.search("products/([\S]+)/", response.url)
        return sku.group(1) if sku else None

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        total_matches = is_empty(
            re.findall(r'\d+', response.xpath('//a[@id="active-1"]//text()').extract()[0], re.DOTALL), 0
        )

        if total_matches:
            return int(total_matches)
        else:
            return 0

    def _scrape_results_per_page(self, response):
        return self.items_per_page

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath(
            '//div[contains(@id,"item_")]//'
            'a[contains(@onclick,"irwStatTopProductClicked")]/@href').extract()

        if items:
            for item in items:
                link = "http://www.ikea.com%s" % item
                res_item = SiteProductItem()
                yield link, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        items = response.xpath(
            '//div[contains(@id,"item_")]//'
            'a[contains(@onclick,"irwStatTopProductClicked")]/@href').extract()
        if len(items) < 1:
            return

        self.current_page += 1
        if "&pageNumber=" in response._url:
            url = response._url.replace("&pageNumber="+str(self.current_page-1),
                                        "&pageNumber="+str(self.current_page))
        else:
            url = response._url + "&pageNumber=" + str(self.current_page)

        if url:
            return url
        else:
            self.log("Found no 'next page' links", DEBUG)
            return None
