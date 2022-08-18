#!/usr/bin/python

import re
import json
import requests
import traceback

from extract_data import Scraper

class MenardsScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is https://www.menards.com/.*/"
    PRODUCT_URL = 'https://service.menards.com/ProductDetailsService/services/cxf/rest/v5/getInitialized/storeNumber/3598/machineType/external/sourceId/999/fulfillmentStoreNumber/3205?' \
                  'itemIds={product_id}'

    def __init__(self, **kwargs):  # **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)
        self.product_json = None

    def check_url_format(self):
        m = re.match(r"^https://www.menards.com/.*?$", self.product_page_url)
        return bool(m)

    def _extract_page_tree(self):
        for i in range(self.MAX_RETRIES):
            try:
                product_id = re.findall(r'p-(\d+)', self.product_page_url)
                if not product_id:
                    return None
                product_url = self.PRODUCT_URL.format(product_id=product_id[0])
                product_json = requests.get(url=product_url, timeout=20).json()
                if not product_json.get('itemMap').get(product_id[0]):
                    return None
                self.product_json = product_json.get('itemMap').get(product_id[0])
                return
            except:
                print traceback.format_exc()

    def not_a_product(self):
        if not self.product_json:
            return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _product_id(self):
        product_id = self.product_json.get('itemId')
        return product_id if product_id else None

    def _sku(self):
        sku = self.product_json.get('menardsSku')
        return sku if sku else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        title = self.product_json.get('title')
        return title

    def _brand(self):
        brand = self.product_json.get('brandName')
        return brand

    def _product_title(self):
        return self._product_name()

    def _model(self):
        model = self.product_json.get('modelNumber')
        return model

    def _upc(self):
        upc = self.product_json.get('properties, {}').get('UPC')
        return upc

    def _long_description(self):
        long_description = self.product_json.get('longDescription')
        if long_description:
            long_description ='<p>' + long_description + '</p><ul>'
        bullets = self.product_json.get('bullets', [])
        for bullet in bullets:
            long_description += '<li>' + bullet + '</li>'
        long_description += '</ul>'
        return long_description

    def _description(self):
        short_desc = self.product_json.get('longDescription')
        return short_desc

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _image_urls(self):
        images = self.product_json.get('alternateImages', [])
        image_urls = []
        media_path = self.product_json.get('mediaPath')
        if not media_path:
            return None
        for image in images:
            image_url = 'https://hw.menardc.com/main/' + media_path + '/ProductLarge/' + image
            image_urls.append(image_url)
        image = self.product_json.get('image')
        image_url = 'https://hw.menardc.com/main/' + media_path + '/ProductLarge/' + image if image else None
        if image_url:
            image_urls.append(image_url)
        return image_urls

    def _pdf_urls(self):
        media_path = self.product_json.get('mediaPath')
        pdf_properties = self.product_json.get('pdfproperties', [])
        pdf_urls = []
        if not media_path:
            return None
        for pdf in pdf_properties:
            pdf_url = 'https://hw.menardc.com/main/' + media_path + '/' + pdf['propertyName'] + '/' + pdf['pdfFileName']
            pdf_urls.append(pdf_url)
        return pdf_urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.product_json.get('priceAndStatusDTO').get('rebatePriceDisplay')
        if not price:
            price = self.product_json.get('priceAndStatusDTO').get('priceDisplay')
        return price

    def _price_amount(self):
        price = self._price()
        return float(price[1:]) if price else None

    def _price_currency(self):
        return "USD"

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return not(self.product_json.get('available'))

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id": _product_id, \
 \
        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name, \
        "product_title": _product_title, \
        "model": _model, \
        "sku": _sku, \
        "upc": _upc, \
        "description" : _description, \
        "long_description" : _long_description, \
 \
        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls, \
        "pdf_urls": _pdf_urls, \
 \
        # CONTAINER : SELLERS
        "price": _price, \
        "price_amount": _price_amount, \
        "price_currency": _price_currency, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "brand": _brand, \
        }