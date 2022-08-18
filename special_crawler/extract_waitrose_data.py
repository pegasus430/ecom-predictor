#!/usr/bin/python

import re
import requests
import traceback
from extract_data import Scraper

class WaitroseScraper(Scraper):

    API_URL = 'https://www.waitrose.com/api/custsearch-prod/v3/search/-1/{prod_id}?orderId=0'

    AUTH_URL = 'https://www.waitrose.com/api/authentication-prod/v2/authentication/token'

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.waitrose.com/.*"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
            "passkey=ixky61huptwfdsu0v9cclqjuj" \
            "&apiversion=5.5" \
            "&displaycode=17263-en_gb" \
            "&resource.q0=products" \
            "&filter.q0=id:eq:{}" \
            "&stats.q0=reviews"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.prod_json = {}
        self.stock_json = {}

    def check_url_format(self):
        m = re.match("https?://www.waitrose.com/.*", self.product_page_url)
        return bool(m)

    def _extract_page_tree(self):
        for i in range(self.MAX_RETRIES):
            try:
                try:
                    # Get redirect url if there is one
                    self.product_page_url = requests.head(self.product_page_url).headers['location']
                except:
                    pass

                try:
                    authorization = self._request(self.AUTH_URL).json()['loginResult']['jwtString']
                except Exception as e:
                    raise Exception('Error getting authorization: {}'.format(e))

                try:
                    prod_url = self.API_URL.format(prod_id=self._product_id())
                    headers = {'authorization': authorization}
                    prod_json = self._request(prod_url, headers=headers).json()
                    self.prod_json = prod_json['products'][0]
                    stock_json = prod_json.get('conflicts', [])
                    if stock_json:
                        self.stock_json = stock_json[0]
                    return
                except Exception as e:
                    raise Exception('Error getting product json: {}'.format(e))

            except Exception as e:
                if self.lh:
                    self.lh.add_list_log('errors', str(e))

                print traceback.format_exc()

        self.is_timeout = True

    def not_a_product(self):
        if not self.prod_json:
            return True
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.product_page_url.split('?')[0].split('/')[-1]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.prod_json['name']

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        return self.prod_json['summary']

    def _long_description(self):
        return self.prod_json['contents']['marketingDescBop']

    def _ingredients(self):
        ingredients = self.prod_json['contents']['ingredients'].split(',')
        return [re.sub('<[^>]*?>', '', i).strip() for i in ingredients]

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_url = re.sub(
            r'(?<=/)\d{1,2}(?=/)|(?<=_)\d{1,2}(?=\.)', '11',
            self.prod_json.get('thumbnail', '')
        )
        return [image_url] if image_url else None

    ##########################################
    ################ CONTAINER : REVIEWS
    ##########################################

    def _review_id(self):
        return self._product_id().split('-')[0]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        return self.prod_json['displayPrice']

    def _price_currency(self):
        return "GBP"

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self._no_longer_available():
            return 1

        return 1 if self.stock_json.get('outOfStock', False) else 0

    def _no_longer_available(self):
        return 1 if 'unavailable' in self.stock_json.get('messages', {}).get('reason', '') else 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        return [c['name'] for c in self.prod_json['categories']]

    def _brand(self):
        return self.prod_json['brand']

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "description": _description,
        "long_description": _long_description,
        "ingredients": _ingredients,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "price_currency": _price_currency,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,
        "no_longer_available": _no_longer_available,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
