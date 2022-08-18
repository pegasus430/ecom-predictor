#!/usr/bin/python

import re
import traceback
from extract_data import Scraper

class WalmartGroceryScraper(Scraper):

    INVALID_URL_MESSAGE = 'Expected URL format is http(s)://grocery.walmart.com/.*/product-detail.jsp?skuId=<prod-id> or ' \
                          'http(s)://grocery.walmart.com/product/<prod-id>'

    API_BASE_URL = 'https://grocery.walmart.com/v3/api/products/{0}?itemFields=all&storeId=5884'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_id = None
        self.product_data = {}

        self._set_proxy()

    def check_url_format(self):
        m = re.match('https?://grocery.walmart.com/.*/product-detail.jsp?skuId=(\d+)', self.product_page_url, re.U)
        if not m:
            m = re.match('https?://grocery.walmart.com/product/(?:.*/)?(\d+)', self.product_page_url.split('?')[0])

        if m:
            self.product_id = m.group(1)
            return True

    def _extract_page_tree(self):
        api_url = self.API_BASE_URL.format(self.product_id)

        for i in range(self.MAX_RETRIES):
            try:
                response = self._request(api_url, log_status_code = True)

                if response.ok:
                    self.product_data = response.json()
                    return

                self.ERROR_RESPONSE['failure_type'] = response.status_code

            except Exception as e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', str(e))

        self.is_timeout = True

    def not_a_product(self):
        if not self.product_data:
            return True

    def _product_id(self):
        return self.product_id

    def _product_name(self):
        return self.product_data['basic']['name']

    def _model(self):
        return self.product_data['detailed']['modelNum']

    def _description_helper(self):
        description = self.product_data['detailed']['description']
        if description:
            split_index = description.find('<p>')
            if split_index != -1:
                return (description[:split_index], description[split_index:])
        return (description, None)

    def _description(self):
        return self._description_helper()[0]

    def _long_description(self):
        return self._description_helper()[1]

    def _features(self):
        features = self.product_data['detailed']['specialFeatures']
        if features:
            # match all the commas which are not inside the parenthesis
            # example: 'vruchtensap 5% uit concentraat (limoensap 1,8%, citroensap 1,4%)'
            features = re.split(r',\s*(?![^()]*\))', features)
            return [i.strip() for i in features]

    def _ingredients(self):
        ingredients = self.product_data['detailed'].get('ingredients')
        if ingredients:
            return ingredients.split(',')

    def _image_urls(self):
        return [self.product_data['basic']['image']['large']]

    def _price_amount(self):
        return self.product_data['store']['price']['displayPrice']

    def _in_stock(self):
        if self.product_data['basic']['isOutOfStock']:
            return 0
        return 1

    def _brand(self):
        return self.product_data['detailed'].get('brand')

    DATA_TYPES = {
        "product_id" : _product_id,
        "product_name" : _product_name,
        "description" : _description,
        "long_description" : _long_description,
        "ingredients" : _ingredients,
        "model": _model,
        "features": _features,
        "image_urls" : _image_urls,
        "price_amount" : _price_amount,
        "brand": _brand
        }
