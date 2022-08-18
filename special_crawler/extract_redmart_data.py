#!/usr/bin/python

import re
import traceback
from extract_data import Scraper


class RedmartScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    API_URL = "https://api.redmart.com/v1.6.0/catalog/products/{product_name}" \
              "?mixNmatch=true&pageSize=18&sameBrand=true&similarProduct=true"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
                 "passkey=3aqde2lhhpwod1c1ve03mx30j" \
                 "&apiversion=5.5" \
                 "&displaycode=13815-en_sg" \
                 "&resource.q0=products" \
                 "&filter.q0=id:eq:{}" \
                 "&stats.q0=reviews"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = None

    def not_a_product(self):
        self._extract_product_json()
        return True if not self.product_json else False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_product_json(self):
        try:
            product_name = re.search('product/(.*)', self.product_page_url)
            if product_name:
                product_name = product_name.group(1)
            self.product_json = self._request(self.API_URL.format(product_name=product_name)).json()
            self.product_json = self.product_json['product']
        except Exception as e:
            if self.lh:
                self.lh.add_list_log('errors', str(e))
            print traceback.format_exc(e)

    def _product_id(self):
        return self.product_json['id']

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.product_json['title']

    def _description(self):
        return self.product_json['desc']

    def _sku(self):
        return self.product_json['sku']

    def _manufacturer(self):
        return self.product_json['filters']['mfr_name']

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_list = []
        image_urls = self.product_json['images']
        for image_url in image_urls:
            image_url = 'https://s3-ap-southeast-1.amazonaws.com/media.redmart.com/newmedia/1600x' + image_url['name']
            image_list.append(image_url)
        return image_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.product_json['pricing']['promo_price']
        if not price:
            price = self.product_json['pricing']['price']
        return price

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if not self.product_json['inventory']['stock_status']:
            return 1
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        return self.product_json['filters']['brand_name']

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "description": _description,
        "sku": _sku,
        "manufacturer": _manufacturer,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "brand": _brand
    }
