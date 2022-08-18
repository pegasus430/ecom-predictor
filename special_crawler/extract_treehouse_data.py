#!/usr/bin/python

import re
from product_ranking.guess_brand import guess_brand_from_first_words
import urlparse

from lxml import html
from extract_data import Scraper


class TreeHouseScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://tree.house/shop/<product-name> or " \
                          "http(s)://shop.tree.house/products/<product-name>"

    def check_url_format(self):
        m = re.match("https?://tree.house/shop/.*", self.product_page_url)
        n = re.match("https?://shop.tree.house/products/.*", self.product_page_url)
        return bool(m or n)

    def not_a_product(self):
        type = self.tree_html.xpath('//meta[@property="og:type"]/@content')
        if type:
            return type[0].lower() != 'product'
        return True

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_id(self):
        product_id = self._find_between(html.tostring(self.tree_html), 'product: {"id":', ',"')
        return product_id

    def _product_name(self):
        product_name = self.tree_html.xpath('//h1[@itemprop="name"]/text()')
        return product_name[0] if product_name else None

    def _product_title(self):
        product_title = self.tree_html.xpath('//meta[@property="og:title"]/@content')
        return product_title[0] if product_title else None

    def _title_seo(self):
        return self._product_name()

    def _brand(self):
        product_name = self._product_name()
        brand = guess_brand_from_first_words(product_name)
        return brand if brand else None

    def _description(self):
        short_description = self.tree_html.xpath('//div[@class="product-info"]/h2/text()')
        return short_description[0] if short_description else None

    def _long_description(self):
        long_description = self.tree_html.xpath('//meta[@property="og:description"]/@content')
        return long_description[0]

    def _categories(self):
        categories = self.tree_html.xpath('//*[@class="breadcrumb"]//div[@class="label truncate"]/a/text()')
        return categories if categories else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_list = self.tree_html.xpath('//div[contains(@class,"image-slider")]//img/@src')
        return map(lambda m: urlparse.urljoin('https:', m), image_list)

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.tree_html.xpath('//p[@itemprop="price"]/@content')
        return float(price[0]) if price else None

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        in_stock = self.tree_html.xpath('//link[@itemprop="availability"]/@href')
        if in_stock:
            return 1 if in_stock[0] != 'http://schema.org/InStock' else 0
        return 1

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : PRODUCT_INFO
        "product_id" : _product_id, \
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "description" : _description, \
        "long_description" : _long_description, \
        "categories": _categories, \
        "brand": _brand, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls, \

        # CONTAINER : SELLERS
        "price_amount" : _price_amount, \
        }
