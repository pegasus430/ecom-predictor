#!/usr/bin/python

import re
import json
import time
import requests
import traceback

from lxml import html
from extract_data import Scraper
from shared_cookies import SharedCookies, SharedLock
from product_ranking.guess_brand import guess_brand_from_first_words


class InstaCartScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    HOME_URL = 'https://www.instacart.com/'

    LOG_IN_URL = 'https://www.instacart.com/accounts/login'

    PRODUCT_URL = 'https://www.instacart.com/v3/containers/products/{product_id}'

    ITEMS_URL = 'https://www.instacart.com/v3/containers/items/{item_id}'


    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_data = {}
        self.product_details = {}
        self.product_disclaimer = {}
        self.categories_data = {}

        self.shared_lock = SharedLock('instacart')
        self.shared_cookies = SharedCookies('instacart')

    def _extract_page_tree(self):
        start_time = time.time()
        end_time = start_time
        while end_time-start_time < 30:
            end_time = time.time()
            try:
                if self.shared_lock.load():
                    time.sleep(10)
                else:
                    self.shared_lock.save('1')

                    s = requests.Session()

                    cookies_from_s3 = self.shared_cookies.load()
                    if cookies_from_s3:
                        s.cookies = cookies_from_s3
                    else:
                        s.cookies['_instacart_session'] = 'K1h6d3Z2WC9Na0VhZkVINlQwdEd4Nm1FclFYb2lBbUJKVnUwRHF1cnI' \
                                                          'vaXJINzdwaForRE5ad094VlZQTmF1ZjZDRk9NSERKUVVWdml3TktjV1' \
                                                          'VNYnR0NHpMdGdKTHhnUDVmdFFnWmdyVjRmcm80MlVwZEVCNm96SkRHa' \
                                                          '01lQkJqMXhZU0dINS9ra1lXWWgzVS85a3R0K0ROMHJWNTRvQ3lzZmNm' \
                                                          'WDJVWkRJM0paVWxrT011QjlZVWx1N2RtdnZMOWRFRHNiUXIrUm5KMit' \
                                                          'ycFMvNzRCUnFjUHN5NVNPVU9EVkFzdHBiY2g0M2JrVnNXQW92cjRrWl' \
                                                          'lNd3pSUjlSNFZ0dXQ0OEZob3FHdldQZXRFSlo1clB1OFNWMW5rWmYvV' \
                                                          '3hKUXFJUG1zZVZxSG1DSUJjWVY3dytLb1lqRkRLZWdWMGZqSnJkbGhW' \
                                                          'RmlRS2t5M3VSRGs5QWZhRW5Vbmo2dzdUQlJPYnY1KzNvN0M0NjlPamh' \
                                                          'qczJiSS9jeC9vVUNHaGN3Mi8wcGx0ZUk5dVpIdktGY2lsUUFqeUo4Rz' \
                                                          'RJclJWZnArazFzVUNIR0QvSTdkbGlMWnArMVlaS3NNaUd4Mnl5MTBJa' \
                                                          '3J2VllZdzBpblFOREVoYm1lT0duQ1dqMk9zZmUrQjVrSGNVWnNSR28v' \
                                                          'c2VrcTV4Uk1KZXhMNzVrcTktLVZURDd0Wm5yVU0xNk5BTm1PU3F3T0E' \
                                                          '9PQ%3D%3D--5be4d957d70c5c29da7f0f6a7652ba059d7fbb62'
                        self.shared_cookies.save(s)

                    try:
                        if 'products/' in self.product_page_url:
                            product_id = re.search('products/(.*)', self.product_page_url.split('?')[0])
                            product_id = re.search('\d+', product_id.group(1)).group()
                            product_data = self._request(self.PRODUCT_URL.format(product_id=product_id), session=s).json()
                        elif 'items/' in self.product_page_url:
                            items_id = re.search('items/(.*)', self.product_page_url.split('?')[0]).group(1)
                            product_data = self._request(self.ITEMS_URL.format(item_id=items_id), session=s).json()

                            # if it's an error response, try again with the redirected url
                            # (don't redirect by default, because sometimes there is no price)
                            if product_data.get('container', {}).get('title') == 'Not Found':
                                redirect_url = self._request(self.product_page_url, verb='head', use_proxies=False).url
                                if not redirect_url == 'https://www.instacart.com/':
                                    self.product_page_url = redirect_url
                                continue

                    except Exception as e:
                        raise Exception('Error getting product_data: {}'.format(e))

                    self.shared_lock.save('')

                    message = product_data.get('error', {}).get('message')
                    if message:
                        raise Exception('Got error message: {}'.format(message))

                    self.product_data = product_data.get('container', {}).get('modules')

                    if not self.product_data:
                        raise Exception('Got product data: {}'.format(product_data))

                    for product in self.product_data:
                        if 'details' in product.get('data', {}):
                            self.product_details = product.get('data', {})
                        if 'disclaimer' in product.get('data', {}):
                            self.product_disclaimer = product.get('data', {}).get('disclaimer')
                        if 'breadcrumbs' in product.get('data', {}):
                            self.categories_data = product.get('data', {}).get('breadcrumbs', {})
                    for product in self.product_data:
                        if 'item' in product.get('data', {}):
                            self.product_data = product.get('data', {}).get('item', {})
                        elif 'product' in product.get('data', {}):
                            self.product_data = product.get('data', {}).get('product', {})

                    if self.not_a_product():
                        continue

                    return

            except Exception as e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', str(e))

                self.shared_lock.save('')

            self.shared_lock.save('')

    def not_a_product(self):
        if not self.product_data:
            return True
        return False

    def _product_id(self):
        product_id = re.search('\d+', self.product_data['id'])
        return product_id.group() if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.product_data['name']

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _model(self):
        return self._product_id()

    def _description(self):
        description = self.product_disclaimer
        if not description and self.product_details.get('nutrition', {}).get('discliaimer', ''):
            description = self.product_details.get('nutrition', {}).get('disclaimer')
        return description if description else None

    def _long_description(self):
        details = None
        for data in self.product_details.get('details', {}):
            if 'details' in data.get('header').lower():
                details = data.get('body')
        return details

    def _ingredients(self):
        ingredients = None
        for data in self.product_details.get('details', {}):
            if 'ingredients' in data.get('header').lower():
                ingredients = data.get('body')
        if ingredients:
            return [i.strip() for i in ingredients.split(',') if ingredients]

    def _directions(self):
        directions = None
        for data in self.product_details.get('details', {}):
            if 'directions' in data.get('header').lower():
                directions = data.get('body')
        return directions

    def _categories(self):
        categories = [cat.get('title') for cat in self.categories_data if cat.get('title')]
        if categories:
            return categories

    def _nutrition_facts(self):
        nutrition_facts = []
        if self.product_details.get('nutrition'):
            nutrition_data = self.product_details.get('nutrition').copy()
            nutrients = nutrition_data.pop('nutrients', [])
            for key, value in nutrition_data.items():
                nutrition_facts.append('{}: {}'.format(key, value))
            for fact in nutrients:
                if fact.get('label') and fact.get('total'):
                    nutrition_facts.append('{}: {}'.format(fact.get('label'), fact.get('total')))
                    for sub_fact in fact.get('subcategories', []):
                        if sub_fact.get('label') and sub_fact.get('total'):
                            nutrition_facts.append('{}: {}'.format(sub_fact.get('label'), sub_fact.get('total')))
        return nutrition_facts if nutrition_facts else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_url = self.product_data.get('image_list', {})
        image_urls = [img.get('url') for img in image_url if len(img.get('url')) > 0]
        return image_urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        return self.product_data.get('pricing', {}).get('price')

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if 'items/' in self.product_page_url:
            return 0 if self._price() else 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        return guess_brand_from_first_words(self._product_title())

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
        "model": _model,
        "description": _description,
        "long_description": _long_description,
        "ingredients": _ingredients,
        "directions": _directions,
        "categories": _categories,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "brand": _brand,
        }
