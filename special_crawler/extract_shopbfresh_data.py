#!/usr/bin/python

import re
import json
import requests
import traceback

from product_ranking.guess_brand import guess_brand_from_first_words
from extract_data import Scraper


class ShopBfreshScraper(Scraper):
    INVALID_URL_MESSAGE = "Expected URL format is http(s)://shop.bfresh.com/en/*"

    QUERY_URL = "https://shop.bfresh.com/api/query.json"

    HEADERS = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest'
    }

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_data = {}

    def _extract_page_tree(self):
        for i in range(3):
            try:
                with requests.Session() as s:
                    product_id = self._extract_id_from_url(self.product_page_url)
                    post_id = 'product_{}_full'.format(product_id)
                    data = json.dumps({
                        "meta": {},
                        "request": [
                            {
                                "args": {
                                    "store_id": "00034100",
                                    "eans": [product_id]
                                },
                                "v": "0.1",
                                "type": "product.details",
                                "id": post_id
                            }
                        ]
                    })
                    response = s.post(self.QUERY_URL, data=data, headers=self.HEADERS)

                    if response.ok:
                        content = response.json()
                        self.product_data = content['responses'][0]['data']['items'][0]
                        return
                    else:
                        self.ERROR_RESPONSE['failure_type'] = response.status_code
            except:
                print traceback.format_exc()

        self.is_timeout = 1

    def _extract_id_from_url(self, url):
        product_id = re.findall(r'(?<=/)(.*?)(?=/.+\Z)', url)
        return product_id[-1] if product_id else None

    def check_url_format(self):
        m = re.match(r"^https?://shop.bfresh.com/en/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        return True if not self.product_data else False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.product_data.get('ean')

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.product_data.get('name')

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _nutrition_facts(self):
        return self.product_data.get('nutrition_facts')

    def _ingredients(self):
        return self.product_data.get('ingredients')

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        images = self.product_data.get('images', [])
        image_urls = []
        for img in images:
            if 's1350x1350' in img:
                image_urls.append(img.get('s1350x1350'))
            else:
                image_urls.append(img.get('s350x350'))
        if not image_urls:
            image_urls.append(self.product_data.get('main_image', {}).get('s350x350'))

        return image_urls if image_urls else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.product_data.get('price')
        return float(price) / 100 if price else None

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return not (self.product_data.get('available'))

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        brand = self.product_data.get('extended_info', {}).get('tm')
        title = self._product_title()
        if not brand and title:
            brand = guess_brand_from_first_words(title)

        return brand

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "ingredients": _ingredients,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "brand": _brand
        }
