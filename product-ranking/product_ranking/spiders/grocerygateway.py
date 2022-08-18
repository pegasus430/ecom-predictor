# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import urlparse
import traceback

from scrapy.log import INFO

from product_ranking.items import (SiteProductItem, Price)
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty


class GroceryGatewayProductsSpider(BaseValidator, BaseProductsSpider):

    name = 'grocerygateway_products'
    allowed_domains = ["grocerygateway.com"]

    SEARCH_URL = "https://www.grocerygateway.com/store/groceryGateway/en/" \
                 "search//loadMore?text={search_term}&page={page_num}&q={search_term}&current={offset}&sort=relevance"


    def __init__(self, *args, **kwargs):
        formatter = FormatterWithDefaults(page_num=0, offset=0)
        super(GroceryGatewayProductsSpider, self).__init__(formatter, *args, **kwargs)
        self.current_page = 0

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
        if not brand:
            brand = guess_brand_from_first_words(product.get('title'))
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse upc
        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc, conv=string.strip)

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

        #Parse price_per_volume
        price_per_volume = self._parse_price_per_volume(response)
        cond_set_value(product, 'price_per_volume', price_per_volume)

        #Parse volume_measure
        volume_measure = self._parse_volume_measure(response)
        cond_set_value(product, 'volume_measure', volume_measure)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        return product

    @staticmethod
    def _parse_title(response):
        title = is_empty(response.xpath('//h1[@class="name"]/text()').extract())
        return title

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//meta[@itemprop="brand"]/@content').extract()
        if brand:
            return brand[0]

    @staticmethod
    def _parse_upc(response):
        upc = re.search('UPC #: (.*?)<', response.body, re.DOTALL)
        if not upc:
            upc = re.search('>UPC</h3> #: (.*?)<', response.body, re.DOTALL)
        if upc:
            upc = upc.group(1)
            return upc[-12:].zfill(12)

    @staticmethod
    def _parse_out_of_stock(response):
        out_of_stock = response.xpath('//*[@itemprop="availability"]/@href').extract()
        if out_of_stock:
            out_of_stock = out_of_stock[0].lower()
        if 'instock' in out_of_stock:
            return False
        return True

    @staticmethod
    def _parse_categories(response):
        category_list = []
        categories = re.search('en/(.*?)/p', response.url, re.DOTALL)
        if categories:
            categories = categories.group(1).split('/')
            for cat in categories:
                category_list.append(cat.replace('-', ' '))
        return category_list[:-1]

    def _parse_price(self, response):
        currency = "USD"
        price = is_empty(response.xpath('//meta[@itemprop="price"]/@content').extract())
        try:
            return Price(price=float(price.replace("$", '')), priceCurrency=currency)
        except:
            self.log("Parse price error {}".format(traceback.format_exc()))

    @staticmethod
    def _parse_price_per_volume(response):
        volume_data = response.xpath('//span[@class="actualPrice"]/text()').re(r'\((.*?)\)')
        return volume_data[0].split('/')[0] if volume_data and '/' in volume_data[0] else None

    @staticmethod
    def _parse_volume_measure(response):
        volume_data = response.xpath('//span[@class="actualPrice"]/text()').re(r'\((.*?)\)')
        return volume_data[0].split('/')[1] if volume_data and '/' in volume_data[0] else None

    @staticmethod
    def _parse_image_url(response):
        image_url = is_empty(response.xpath('//meta[@itemprop="image"]/@content').extract())
        return image_url

    @staticmethod
    def _parse_description(response):
        desc = response.xpath('//div[contains(@class, "description light")]//text()').extract()
        desc = ''.join(desc)
        return desc

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        totals = response.xpath('//*[@name="totalNumberOfResults"]/@value').extract()
        try:
            return int(totals[0])
        except:
            self.log("Found no total_matches {}".format(traceback.format_exc()))

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//ul[contains(@class, "products-gallery")]'
                               '/li//a[contains(@class, "product-card__thumb")]/@href').extract()

        if items:
            for item in items:
                res_item = SiteProductItem()
                item = urlparse.urljoin(response.url, item)
                yield item, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        try:
            page_count = int(response.xpath('//*[@name="numberOfPages"]/@value')[0].extract())
            if self.current_page >= page_count:
                return

            self.current_page += 1
            next_link = self.SEARCH_URL.format(search_term=response.meta.get('search_term'),
                                               page_num=self.current_page, offset=self.current_page * 24)
            return next_link
        except:
            self.log("Found no next link {}".format(traceback.format_exc()))
            return