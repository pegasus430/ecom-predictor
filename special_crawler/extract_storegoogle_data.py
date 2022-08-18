#!/usr/bin/python
# -*- coding: utf-8 -*-

import re

from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words


class StoreGoogleScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://store.google.com/.*"

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^https?://store.google.com/.*$", self.product_page_url)
        return not not m

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """
        if len(self.tree_html.xpath('//div[contains(@class, "page-module")]')) < 1:
            return True

        return False

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath('//div[contains(@class, "title-price-container")]'
                                            '/h1[@itemprop="name"]/text()')
        if product_name:
            return product_name[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        short_description = self.tree_html.xpath('//meta[@name="description"]/@content')
        if short_description:
            return short_description[0]

    def _brand(self):
        brand = self.tree_html.xpath('//meta[@itemprop="brand"]/@content')
        if brand:
            return brand[0]
        return guess_brand_from_first_words(self._product_name())

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//ul[contains(@class, "pagination-list")]'
                                          '/li//div/@data-default-src')
        return image_urls

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath('//div[@class="description-text"]'
                                     '//span[@class="is-price"]/text()')
        if price:
            price = price[0]
            if 'From' in price:
                price = re.search('From (.*)', price, re.DOTALL)
                if price:
                    price = price.group(1)
            if 'month' in price:
                price = re.search('(.*?) ', price, re.DOTALL)
                if price:
                    price = price.group(1)
            return price

    def _price_amount(self):
        price = self._price()
        price = re.search('\d+\.?\d+', price).group()
        return float(price)

    def _price_currency(self):
        price = self._price()
        if '$' in price:
            return 'USD'

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo": _title_seo, \
        "description": _description, \
        "brand": _brand, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count": _image_count,\
        "image_urls": _image_urls, \

        # CONTAINER : SELLERS
        "price": _price, \
        "price_amount": _price_amount, \
        "price_currency": _price_currency, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "marketplace": _marketplace, \
        }
