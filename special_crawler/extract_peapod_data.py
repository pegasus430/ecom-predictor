#!/usr/bin/python

import re
import json
import time

import requests
import traceback
from lxml import html

from extract_data import Scraper
from shared_cookies import SharedCookies


class PeapodScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is https://www.peapod.com/modal/item-detail/{product_id}"

    TWOCAPTCHA_APIKEY = "e1c237a87652d7d330c189f71c00ec0b"

    SOLVE_CAPTCHA_API = "http://2captcha.com/in.php?key={}&method=userrecaptcha&googlekey={}&pageurl={}"
    SOLVED_CAPTCHA_API = "http://2captcha.com/res.php?key={}&action=get&id={}"
    SUBMIT_CAPTCHA_URL = "https://www.peapod.com/cdn-cgi/l/chk_captcha?id=340cbc7dda0a5996&g-recaptcha-response={}"

    REQUEST_HEADERS = {'Content-Type': 'application/json;charset=UTF-8',
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://www.peapod.com',
            "Referer": "https://www.peapod.com/",
            'Host': 'www.peapod.com'}

    ZIP_CODES = ['10005', '20001', '19150', '60007', '07001']

    START_URL = "https://www.peapod.com/"
    SET_ZIP_URL = 'https://www.peapod.com/api/v2.0/user/guest?customerType=C&zip={zipcode}'

    PRODUCT_URL = "https://www.peapod.com/api/v2.0/user/products/{product_id}" \
                  "?extendedInfo=true&flags=true&nutrition=true&substitute=true"

    ADDITIONAL_INFO = "https://ondemand.itemmaster.com/jsons/{product_id}.json"

    REVIEW_URL = "https://api.bazaarvoice.com/data/reviews.json?apiVersion=5.4" \
                 "&filter=ProductId:{}&include=Products" \
                 "&passKey=74f52k0udzrawbn3mlh3r8z0m&stats=Reviews"

    def __init__(self, disable_shared_cookies=False, **kwargs):
        Scraper.__init__(self, **kwargs)

        self._set_proxy()

        self.product_data = {}
        self.additional_product_data = {}

        self.shared_cookies = SharedCookies('peapod')

        self.require_new_session = False
        self.zip_codes = self.ZIP_CODES
        self.try_zip = 0 # zipcode in zip_codes to try (start with 0)

        if kwargs.get('zip_code'):
            self.zip_codes = [kwargs['zip_code']] + self.zip_codes
            self.require_new_session = True

    def check_url_format(self):
        m = re.match(r"^https://www\.peapod\.com/modal/item-detail/\d+", self.product_page_url)
        return bool(m)

    def _extract_page_tree(self):
        shared_cookies_valid = True

        i = 0

        while i < 3 and self.try_zip < len(self.zip_codes):
            i += 1
            try:
                with requests.Session() as self.s:
                    self.product_id = self.get_product_id()

                    # If session is expired
                    if self.require_new_session:
                        # Then create guest account in the right zip code
                        self._request(self.START_URL, session=self.s)
                        try:
                            self.set_zipcode()
                        except Exception as e:
                            print traceback.format_exc()

                            if self.lh:
                                self.lh.add_list_log('errors', 'Error setting zip code: {}'.format(str(e)))

                            i -= 1 # decrement i so we can keep trying
                            self.try_zip += 1

                            continue

                    # Otherwise, try using shared cookies
                    elif shared_cookies_valid:
                        s3_cookies = self.shared_cookies.load()
                        if s3_cookies:
                            self.s.cookies = s3_cookies

                    # Otherwise, assume captchas
                    else:
                        google_captcha_key = self.get_captcha_key_from_start_url()
                        captcha_id = self.get_captcha_id_from_2captcha(google_captcha_key)
                        captcha_code = self.get_captcha_answer_from_2captcha(captcha_id)
                        self.submit_captcha_answer(captcha_code)

                    self.require_new_session = False

                    # Get product data
                    try:
                        self.product_data = self.get_product_data()
                    except Exception as e:
                        self.require_new_session = True

                        if 'No Product found' in str(e):
                            i -= 1 # decrement i so we can keep trying
                            self.try_zip += 1

                        continue

                    if self.product_data:
                        url = self.ADDITIONAL_INFO.format(product_id=self.product_id)
                        self.additional_product_data = self._request(url, session=self.s, use_proxies=False).json()

                    # Only save cookies if original zip code was used
                    if self.try_zip == 0 and len(self.zip_codes) == len(self.ZIP_CODES):
                        self.shared_cookies.save(self.s)

                    return

            except Exception as e:
                shared_cookies_valid = False

                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', str(e))

        self.is_timeout = True # return failure

    def submit_captcha_answer(self, captcha_code):
        self._request(self.SUBMIT_CAPTCHA_URL.format(captcha_code),
              session=self.s,
              headers={"Referer": "https://www.peapod.com/"},
              use_proxies=False)

    def get_captcha_answer_from_2captcha(self, captcha_id, retry=0):
        try:
            page = self._request(self.SOLVED_CAPTCHA_API.format(self.TWOCAPTCHA_APIKEY, captcha_id),
                                 session=self.s,
                                 use_proxies=False)
        except:
            answer = None
        else:
            answer = self.get_captcha_code(page.text)

        if not answer and retry < 10:
            time.sleep(10)
            return self.get_captcha_answer_from_2captcha(captcha_id, retry + 1)
        else:
            return answer

    def get_captcha_id_from_2captcha(self, google_captcha_key):
        page = self._request(self.SOLVE_CAPTCHA_API.format(self.TWOCAPTCHA_APIKEY,
                                                   google_captcha_key,
                                                   self.START_URL),
                             session=self.s,
                             use_proxies=False)
        return self.get_captcha_id(page.text)

    def get_captcha_key_from_start_url(self):
        page = self._request(self.START_URL,
                     session=self.s)
        tree = html.fromstring(page.content)
        return self.extract_captcha_key(tree)

    def set_zipcode(self):
        payload = {"customerType": "C", "zip": self.zip_codes[self.try_zip]}

        r = self._request(self.SET_ZIP_URL.format(zipcode=self.zip_codes[self.try_zip]),
                   session=self.s,
                   verb='post',
                   headers=self.REQUEST_HEADERS,
                   data=json.dumps(payload))

        payload["cityId"] = r.json()['response']['cities'][0]['cityId']

        self._request(self.SET_ZIP_URL.format(zipcode=self.zip_codes[self.try_zip]),
               session=self.s,
               verb='post',
               headers=self.REQUEST_HEADERS,
               data=json.dumps(payload))

    def get_product_data(self):
        page = self._request(self.PRODUCT_URL.format(product_id=self.product_id),
                     session=self.s,
                     headers=self.REQUEST_HEADERS,
                     log_status_code=True)

        response = page.json().get('response', {})

        if response.get('result') == 'ERROR':
            raise Exception(response.get('msg') or 'Error getting product data')

        return response.get('products', [{}])[0]

    def extract_captcha_key(self, tree):
        google_captcha_key = tree.xpath("//div/div/div/iframe/@src")
        if google_captcha_key:
            google_captcha_key = google_captcha_key[0].split("k=")[-1]
            print 'Sent captcha key: {}'.format(google_captcha_key)
            return google_captcha_key

    def get_captcha_id(self, text):
        if "OK" in text:
            code = text.split("|")[-1]
            print 'Got captcha id: {}'.format(code)
            return code

    def get_captcha_code(self, text):
        if "OK" in text:
            solved_code = text.split("|")[-1]
            print 'Got captcha code: {}'.format(solved_code)
            return solved_code

    def get_product_id(self):
        product_id = re.search(r'/(\d+)', self.product_page_url)
        return product_id.group(1) if product_id else None

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.product_data.get('prodId')

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _ingredients(self):
        product = self.additional_product_data.get(self.product_id, {}).get('Product')
        if product:
            ingredients = product[0].get('Ingredients')
            if ingredients:
                return [i.strip() for i in ingredients.split(',')]

    def _product_name(self):
        return self.product_data.get("name")

    def _upc(self):
        upc = self.product_data.get('upc')
        return upc.zfill(12) if upc else None

    def _bullets(self):
        bullet_data = self.additional_product_data.get(self.product_id, {}).get('Custom Content', {}).get('Bullet Points')
        if bullet_data:
            return '\n'.join([x['Bullet'].strip() for x in bullet_data])

    def _description(self):
        description = self.additional_product_data.get(self.product_id, {}).get('Sell Copy')
        if description:
            return re.sub(r'</?p>', '', description)

    def _shelf_description(self):
        shelf_description = ''
        shelf_description += self.additional_product_data.get(self.product_id, {}).get('Marketing Description', '')
        shelf_description += self.additional_product_data.get(self.product_id, {}).get('Other Description', '')
        if shelf_description:
            return shelf_description

    def _nutrition_facts(self):
        nutrition_facts = []
        for key, value in self.product_data.get('nutrition', {}).iteritems():
            if not any(x in key for x in ['Unit', 'Pct', 'Show']):
                nutrition_facts.append((key, value))
        return nutrition_facts if nutrition_facts else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        order = ['A1A3', 'A1L1', 'A1R1', 'A1C1', 'A2C1', 'A3C1', 'A7C1', 'A8C1', 'A9C1']
        media = self.additional_product_data.get(self.product_id, {}).get('Media', [])
        try:
            media.sort(key=lambda x: order.index(x['Image View'][-4:]))
        except ValueError:
            print 'Can not sort the list above, please check new order' \
                  ' on https://www.peapod.com/shop/dist/js/project-newman-user_14f46fffb5316190.js'
        images = [_media.get('url') for _media in media]
        images = filter(lambda i: not '&kb=100' in i, images)

        image_custom = self.additional_product_data.get(self.product_id, {}).get('Custom Content', {}).get('images', [])
        if image_custom:
            for img in image_custom:
                images.append(img.get('Path'))

        image_append = self.additional_product_data.get(self.product_id, {}).get('Retailer Supplied Images')
        if image_append:
            for img in image_append:
                images.append(img.get('Url'))

        if not images:
            image_url = self.product_data.get('image', {}).get('xlarge')
            images = [image_url] if image_url else []

        if images:
            return images

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _review_id(self):
        return self.product_data.get('reviewId')

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        if not self._no_longer_available():
            return self.product_data.get('price')

    def _in_stores(self):
        return 0

    def _marketplace(self):
        return 0

    def _site_online(self):
        if not self._no_longer_available():
            return 1

    def _site_online_out_of_stock(self):
        if self._site_online():
            return self.product_data.get('productFlags', {}).get('outOfStock')

    def _no_longer_available(self):
        if self.try_zip or not self.product_data:
            return 1
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        if self.product_data:
            return [self.product_data.get('rootCatName'), self._category_name()]

    def _category_name(self):
        return self.product_data.get('subcatName')

    def _brand(self):
        return self.product_data.get('brand')

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "ingredients": _ingredients,
        "product_name" : _product_name,
        "upc": _upc,
        "bullets": _bullets,
        "description": _description,
        "shelf_description": _shelf_description,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,

        # CONTAINER : SELLERS
        "price_amount" : _price_amount,
        "in_stores" : _in_stores,
        "marketplace" : _marketplace,
        "site_online" : _site_online,
        "site_online_out_of_stock" : _site_online_out_of_stock,
        "no_longer_available" : _no_longer_available,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "category_name" : _category_name,
        "brand" : _brand,
        }
