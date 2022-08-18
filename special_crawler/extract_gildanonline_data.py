#!/usr/bin/python

import re
import json

from lxml import html
from extract_data import Scraper

class GildanOnlineScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://gildanonline.com/<product-name>"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.product_json = None

    def check_url_format(self):
        m = re.match(r"^http://gildanonline.com/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        self._extract_product_json()
        return False

    def _product_id(self):
        product_id = self.product_json['product_attributes']['sku']
        return product_id.strip() if product_id else None

    def _extract_product_json(self):
        try:
            product_json_text = re.search('{"product_attributes":.*?};', html.tostring(self.tree_html), re.DOTALL).group()[:-1].strip()
            self.product_json = json.loads(product_json_text)
        except:
            self.product_json = None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.tree_html.xpath("//h1[@itemprop='name']/text()")[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _description(self):
        rows = self.tree_html.xpath("//meta[@name='description']/@content")
        return self._clean_text(rows[0]) if rows else None

    def _long_description(self):
        rows = self.tree_html.xpath("//div[@id='tab-description']/ul[@class='features']")
        return html.tostring(rows[0]) if rows else None

    def _swatches(self):
        swatches = []
        color_list = self.tree_html.xpath("//span[@class='form-option-variant form-option-variant--pattern']/@title")
        for img in self._image_urls():
            if color_list:
                color_list = [r for r in list(set(color_list)) if len(r.strip()) > 0]
            for color in color_list:
                swatch = {
                    'color': color,
                    'hero': 1,
                    'hero_image': img
                }
                swatches.append(swatch)

        if swatches:
            return swatches

    def _no_longer_available(self):
        return 0

    def _image_urls(self):
        image_urls = self.tree_html.xpath("//a[@class='productView-thumbnail-link']/@href")
        return image_urls if image_urls else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        return self.tree_html.xpath("//meta[@itemprop='price']/@content")[0]

    def _price(self):
        if self._price_amount():
            price = '$' + str(self._price_amount())
            return price

    def _price_currency(self):
        return self.tree_html.xpath("//meta[@itemprop='priceCurrency']/@content")[0]

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//ul[@class='breadcrumbs']/li/a/text()")

        return categories[1:] if categories else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id": _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name, \
        "product_title": _product_title, \
        "title_seo": _title_seo, \
        "description": _description, \
        "long_description": _long_description, \
        "no_longer_available": _no_longer_available, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls, \

        # CONTAINER : SELLERS
        "price": _price, \
        "price_amount": _price_amount, \
        "price_currency": _price_currency, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "in_stores_out_of_stock": _in_stores_out_of_stock, \
        "marketplace": _marketplace, \

        # CONTAINER : CLASSIFICATION
        "categories": _categories, \
        }
