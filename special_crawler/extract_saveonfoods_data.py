#!/usr/bin/python

import re
from lxml import html

from extract_data import Scraper


class SaveonfoodsScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://shop.saveonfoods.com/store/.*"

    API_URL = 'https://shop.saveonfoods.com/api/product/v7/product/store/{store_id}/sku/{sku}'

    STORE_ID = 'D28B1082'

    HEADERS = {
        'Host': 'shop.saveonfoods.com',
        'Accept': 'application/vnd.mywebgrocer.product+json',
        'X-Requested-With': 'XMLHttpRequest'
    }

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = None

    def check_url_format(self):
        m = re.match(r"https?://shop.saveonfoods.com/store/.*?", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        self._extract_product_json()
        if self.product_json:
            return False

        return True

    def _extract_product_json(self):
        auth_token = self._find_between(html.tostring(self.tree_html), 'Token":"', '"')
        sku = re.search(r'sku/(\d+)', self.product_page_url)

        if auth_token and sku:
            sku = sku.group(1)
            self.HEADERS.setdefault('Authorization', auth_token)
            self.product_json = self._request(self.API_URL.format(store_id=self.STORE_ID, sku=sku)).json()

        return self.product_json

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.product_json.get('Id')

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.product_json.get('Name')

    def _brand(self):
        return self.product_json.get('Brand')

    def _product_title(self):
        return self._product_name()

    def _description(self):
        return self.product_json.get('Description')

    def _no_longer_available(self):
        return 0

    def _sku(self):
        return self.product_json.get('Sku')

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []
        images = self.product_json.get('ImageLinks', [])
        for image in images:
            if image.get('Rel') == 'large' and image.get('Uri'):
                image_urls.append(image['Uri'])

        return image_urls if image_urls else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        return self.product_json.get('CurrentPrice')

    def _in_stores(self):
        return int(self.product_json.get('IsAvailableInStore', False))

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return int(not self.product_json.get('InStock', False))

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        return [self.product_json['Category']] if self.product_json.get('Category') else None

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "brand" : _brand,
        "description" : _description,
        "no_longer_available" : _no_longer_available,
        "sku": _sku,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,

        # CONTAINER : SELLERS
        "price" : _price,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        }
