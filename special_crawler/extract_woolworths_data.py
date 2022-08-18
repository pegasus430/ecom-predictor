#!/usr/bin/python

import re
import requests

from extract_data import Scraper

class WoolworthsScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = 'Expected URL format is http(s)://www.woolworths.com.au/shop/productdetails/<prod-id>/<prod-name> (case insensitive)'

    API_URL = "https://www.woolworths.com.au/apis/ui/product/detail/{}?validateUrl=false"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.product_json = None
        self.product_id = None

    def check_url_format(self):
        m = re.match('https?://www.woolworths.com.au/shop/productdetails/(\d+)/.*', self.product_page_url, re.I)
        if m:
            self.product_id = m.group(1)
        return bool(m)

    def not_a_product(self):
        try:
            self.product_json = requests.get(self.API_URL.format(self.product_id), timeout=10).json()
        except:
            return True
        return False

    def _product_id(self):
        return self.product_json['Product']['Stockcode']

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _image_urls(self):
        return self.product_json['DetailsImagePaths']

    def _ingredients(self):
        ingredients = self.product_json['AdditionalAttributes']['ingredients']
        if ingredients:
            return [i.strip() for i in ingredients.split(',')]

    def _product_name(self):
        return self.product_json['Product']['Description'].strip()

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _model(self):
        return self.product_json['Product']['Stockcode']

    def _description(self):
        return self.product_json['Product']['RichDescription']

    def _no_longer_available(self):
        return 0

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        return self.product_json['Product']['Price']

    def _price_currency(self):
        return 'USD'

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _temp_price_cut(self):
        if self.product_json['Product']['WasPrice'] > self._price_amount():
            return 1
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        return self.product_json['Product']['Brand']

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
        "model": _model, \
        "description" : _description, \
        "no_longer_available": _no_longer_available, \
        "ingredients": _ingredients, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls, \

        # CONTAINER : SELLERS
        "price_amount": _price_amount, \
        "price_currency": _price_currency, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "temp_price_cut": _temp_price_cut, \

        # CONTAINER : CLASSIFICATION
        "brand": _brand, \
        }
