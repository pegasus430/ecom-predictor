#!/usr/bin/python

import re
import json
import time
import requests
import traceback

from extract_data import Scraper
from shared_cookies import SharedCookies, SharedLock
from product_ranking.guess_brand import guess_brand_from_first_words


class KrogerScraper(Scraper):

    ##########################################
    # PREP
    ##########################################

    INVALID_URL_MESSAGE = 'http(s)://www.kroger.com/p/<prod-name>/<prod-id>'

    AUTH_URL = 'https://www.kroger.com/user/authenticate'
    HEADERS = {
        'Content-Type': 'application/json;charset=utf-8',
        'User-Agent': 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'
    }

    STORE_SEARCH_URL = 'https://www.kroger.com/stores?address={zip_code}' \
                       '&maxResults=5&radius=3000&storeFilters=94'
    STORE_PICK_URL = 'https://www.kroger.com/onlineshopping'

    API_URL = 'https://www.kroger.com/products/api/products/details'
    NUTRITION_API = 'https://www.kroger.com/products/api/nutrition/details/{}'

    URL_REGEX = r'^https?://www\.kroger\.com/p/.+?/\d{13}$'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.email = kwargs.get('email') or 'quodro@gmail.com'
        self.password = kwargs.get('password') or 'qwertyaz1'
        self.zip_code = kwargs.get('zip_code') or '45209'

        self.product_json = {}
        self.nutrition_info = {}

        self.shared_lock = SharedLock('kroger')
        self.shared_cookies = SharedCookies('kroger')

    def _login(self, s):
        self.shared_lock.save('1')

        auth_data = {
            'account': {
                'email': self.email,
                'password': self.password,
                'rememberMe': True
            },
            'location': ''
        }

        self._request(self.AUTH_URL, session=s, verb='post', data=json.dumps(auth_data))

        stores = self._request(self.STORE_SEARCH_URL.format(zip_code=self.zip_code), session=s).json()

        if stores:
            store = stores[0]['storeInformation']

            s.cookies['DivisionID'] = store.get('divisionNumber')
            s.cookies['StoreCode'] = store.get('storeNumber')

            self.shared_cookies.save(s)
            self.shared_lock.save('')
        else:
            raise Exception('Stores near zip {} not found'.format(self.zip_code))

        return s.cookies

    def _extract_page_tree(self):
        start_time = time.time()
        end_time = start_time
        while end_time - start_time < 20:
            end_time = time.time()
            try:
                if end_time - start_time > 19:
                    self.shared_lock.save('')

                if self.shared_lock.load():
                    time.sleep(1)
                else:
                    s = requests.Session()

                    cookies_from_s3 = self.shared_cookies.load()
                    if cookies_from_s3:
                        s.cookies = cookies_from_s3
                    else:
                        self._login(s)

                    match = re.search(r'\d{13}', self.product_page_url)
                    if match:
                        upc = match.group()
                        data = json.dumps({'upcs': [upc], 'filterBadProducts': False})
                        product_json = self._request(self.API_URL, session=s, verb='post', data=data).json()
                        self.product_json = product_json['products'][0] if product_json['products'] else {}
                        nutrition_info = self._request(self.NUTRITION_API.format(upc)).json()
                        self.nutrition_info = nutrition_info[0] if nutrition_info else {}
                        if self._product_id():
                            break
                        else:
                            self.shared_cookies.delete()
                    else:
                        raise Exception('UPC not found in url: {}'.format(self.product_page_url))
            except Exception as e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', str(e))

    def check_url_format(self):
        return bool(re.match(self.URL_REGEX, self.product_page_url))

    ##########################################
    # CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.product_json.get('upc')

    ##########################################
    # CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.product_json.get('description')

    def _description(self):
        return self.nutrition_info.get('description')

    def _item_size(self):
        return self.product_json.get('customerFacingSize')

    def _upc(self):
        upc = self.product_json.get('upc')
        if upc:
            return upc[-12:].zfill(12)

    def _no_longer_available(self):
        return not self.product_json

    def _nutrition_fact_helper(self, thing):
        facts = []

        if isinstance(thing, dict):
            if thing.get('title') and 'amount' in thing:
                facts.append({thing['title']: thing['amount']})

            for value in thing.values():
                facts.extend(self._nutrition_fact_helper(value))

        elif isinstance(thing, list):
            for fact in thing:
                facts.extend(self._nutrition_fact_helper(fact))

        return facts

    def _nutrition_facts(self):
        return self._nutrition_fact_helper(self.nutrition_info.get('nutritionFacts', {}))

    def _ingredients(self):
        ingredients = self.nutrition_info.get('ingredients')
        if ingredients:
            return [i.strip() for i in ingredients.split(',')]

    ##########################################
    # CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        """
        CON-43863
        current sort algorithm:
        filter images with max available size
        than move item with `perspective` that equals `mainImagePerspective` to 0 index
        """
        sizes = ['xlarge', 'large', 'medium', 'small', 'thumbnail']
        raw_images = self.product_json.get('images', [])
        images_max_sizes = {}
        for img in raw_images:
            key = img.get('perspective')
            if key not in images_max_sizes.keys():
                images_max_sizes[key] = img.get('size')
            else:
                if sizes.index(images_max_sizes[key]) > sizes.index(img.get('size')):
                    images_max_sizes[key] = img.get('size')

        images = [x for x in self.product_json.get('images', [])
                  if x.get('size') == images_max_sizes.get(x.get('perspective'))]
        for k, image in enumerate(images):
            if image.get('perspective') == self.product_json.get('mainImagePerspective'):
                images.insert(0, images.pop(k))
        return [x.get('url') for x in images] if images else None

    ##########################################
    # CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.product_json.get('priceSale') or \
                self.product_json.get('priceNormal')

        if price:
            return float(price)

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return int(not self.product_json.get('soldInStore', False))

    def _in_stores(self):
        return 1

    ##########################################
    # CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        return self.product_json.get('brandName')

    ##########################################
    # RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        'product_id': _product_id,

        # CONTAINER: PRODUCT_INFO
        'product_name': _product_name,
        'product_title': _product_name,
        'description': _description,
        'item_size': _item_size,
        'upc': _upc,
        "no_longer_available": _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        'image_urls': _image_urls,
        'ingredients': _ingredients,

        # CONTAINER : SELLERS
        'price_amount': _price_amount,
        'site_online': _site_online,
        'site_online_out_of_stock': _site_online_out_of_stock,
        'in_stores': _in_stores,

        # CONTAINER : CLASSIFICATION
        "brand": _brand
        }
