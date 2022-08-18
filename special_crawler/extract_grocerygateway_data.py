# -*- coding: utf-8 -*-
#!/usr/bin/python

import re

from lxml import html
from extract_data import Scraper


class GrocerygatewayScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.grocerygateway.com/store/.*"

    def check_url_format(self):
        m = re.match("^https?://www.grocerygateway.com/store/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[contains(@class, "gtm-product-detail-page")]')) < 1:
            return True

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//h1[@class="name"]/text()')
        return product_name[0]

    def _description(self):
        description = self.tree_html.xpath('//div[@class="description md-pt-40"]//text()')
        description = ''.join(description)

        return self._clean_text(description)

    def _long_description(self):
        description = self.tree_html.xpath('//div[contains(@class, "description light")]//text()')
        description = ''.join(description)

        return self._clean_text(description)

    def _ingredients(self):
        content = html.tostring(self.tree_html)
        if 'Ingredients:' in content:
            ingredient_list = []
            ingredients = re.search('Ingredients:</h3>(.*?)</div>', content, re.DOTALL).group(1).split(',')
            for ingredient in ingredients:
                ingredient_list.append(self._clean_text(ingredient.replace('.', '')))
            return ingredient_list

    def _nutrition_facts(self):
        keys = re.findall(r'\"factType\":\"(.*?)\"', self.page_raw_text)
        return keys if keys else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//ul[contains(@class, "medias-slider__thumbs")]/li//img/@src')

        return image_urls if image_urls else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath('//meta[@itemprop="price"]/@content')
        return '$' + price[0]

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        stock_status = self.tree_html.xpath('//*[@itemprop="availability"]/@href')
        if stock_status and 'instock' in stock_status[0].lower():
            return 0
        return 1

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        category_list = []
        categories = re.search('en/(.*?)/p', self.product_page_url, re.DOTALL).groups(1)
        if categories:
            categories = categories[0].split('/')
            for cat in categories:
                category_list.append(cat.replace('-', ' '))
        return category_list[:-1]

    def _brand(self):
        brand = self.tree_html.xpath('//meta[@itemprop="brand"]/@content')
        if brand:
            return self._clean_text(brand[0])

    def _upc(self):
        upc = re.search('UPC #: (.*?)<', html.tostring(self.tree_html), re.DOTALL).groups(1)
        if not upc:
            upc = re.search('>UPC</h3> #: (.*?)<', html.tostring(self.tree_html), re.DOTALL).groups(1)
        if upc:
            return upc[0][-12:].zfill(12)

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

    DATA_TYPES = {

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "description": _description,
        "long_description": _long_description,
        "upc": _upc,
        "ingredients": _ingredients,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
