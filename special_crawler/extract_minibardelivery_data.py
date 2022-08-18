# -*- coding: utf-8 -*-
#!/usr/bin/python

import re
import requests
import traceback

from lxml import html
from extract_data import Scraper


class MinibarDeliveryScraper(Scraper):

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://minibardelivery.com/store/product/<product-name>"

    WELCOME_URL = 'https://minibardelivery.com'

    AUTH_URL = 'https://minibardelivery.com/api/v2/suppliers?routing_options[product_grouping_ids][]=' \
               '{product_name}&coords[lat]=40.7147682&coords[lng]=-74.0104304'

    PRODUCT_URL = 'https://minibardelivery.com/api/v2/supplier/{supplier_ids}' \
                  '/product_grouping/{product_name}'

    def check_url_format(self):
        m = re.match(r"^(http|https)://minibardelivery.com/store/product/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        self.product_json = None
        self.product_json = self.extract_product_json()

        if not self.product_json:
            return True

        return False

    def extract_product_json(self):
        try:
            client_token = re.search("ClientToken = '(.+?)';", html.tostring(self.tree_html)).group(1)

            if not client_token:
                return None

            headers = {
                'user-agent': self.select_browser_agents_randomly(),
                'authorization': client_token,
            }

            product_name = re.search('product/(.*?)($|/)', self.product_page_url).group(1)

            resp = requests.get(
                self.AUTH_URL.format(product_name=product_name), headers=headers, timeout=5
            ).json()

            supplier_ids = ','.join([str(supplier['id']) for supplier in resp['suppliers']])

            if not supplier_ids:
                return None

            product_json = requests.get(
                self.PRODUCT_URL.format(product_name=product_name, supplier_ids=supplier_ids),
                headers=headers,
                timeout=5
            ).json()

            return product_json

        except Exception as e:
            print('Error Extracting Product Json: {}'.format(traceback.format_exc(e)))

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.product_json.get('id')

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.product_json.get('name')

    def _product_title(self):
        return self.product_json.get('name')

    def _title_seo(self):
        return self.product_json.get('name')

    def _description(self):
        return self.product_json.get('description')

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        return [self.product_json.get('image_url')]

    def _variants(self):
        variants = []
        for v in self.product_json.get('variants'):
            variants.append({
                'in_stock': True if v.get('volume') > 0 else False,
                'price': v.get('price') if v.get('price') else None,
                'properties': {
                    'size': v.get('volume'),
                }
            })

        return variants

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        return float(self.product_json.get('variants')[0].get('price'))

    def _price_currency(self):
        return 'USD'

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _category_name(self):
        return self.product_json.get('category')

    def _brand(self):
        return self.product_json.get('brand')

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id" : _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "description" : _description, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls, \
        "variants" : _variants, \

        # CONTAINER : SELLERS
        "price_amount" : _price_amount, \
        "price_currency" : _price_currency, \
        "site_online" : _site_online, \
        "site_online_out_of_stock" : _site_online_out_of_stock, \

        # CONTAINER : CLASSIFICATION
        "category_name" : _category_name, \
        "brand" : _brand, \

        }
