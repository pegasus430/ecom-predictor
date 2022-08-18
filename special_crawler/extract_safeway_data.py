#!/usr/bin/python

import re
import traceback

import requests
from lxml import html

from extract_data import Scraper


class SafeWayScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://shop.(albertsons or safeway or vons).com/*"

    LOGIN_URL = 'https://shop.safeway.com/bin/safeway/login'

    ZIPCODE_URL = 'https://shop.vons.com/bin/safeway/login'

    PRICE_URL = 'https://shop.vons.com/bin/safeway/product/price?id={}'

    HEADERS = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept-Language': 'en-US,en;q=0.8',
        "Host": "shop.safeway.com",
        "Origin": "https://shop.safeway.com",
        "Referer": "https://shop.safeway.com/ecom/account/sign-in"
    }

    SIGNIN = {
        'resourcePath': '/content/shop/safeway/en/welcome/sign-in/jcr:content'
                        '/root/responsivegrid/column_control/par_0/sign_in',
        'userId': 'laurebaltazar@gmail.com',
        'inputPassword': '12345678'
    }

    ZIPCODE_DATA = {
        'resourcePath': '/content/shop/vons/en/welcome/jcr:content/root/responsivegrid'
                        '/column_control/par_0/two_column_zip_code_',
        'zipcode': '92154'
    }

    SIGNIN_GUEST = {
        'Browse': 'Browse as Guest',
        'Register.ZipCode': None,
        'form': 'ZipCode'
    }

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_id = None
        self.price_data = None

    def check_url_format(self):
        m = re.match('https?://shop.(?:albertsons|safeway|vons).com/(?:.*richInfo_|detail.)(\d+)(.html)', self.product_page_url)
        if m:
            self.product_id = m.group(1)
            return True
        return False

    def _extract_page_tree(self):
        for i in range(3):
            try:
                with requests.Session() as s:
                    self._request(self.LOGIN_URL, data = self.SIGNIN, verb = 'post', session = s)
                    self._request(self.ZIPCODE_URL, data = self.ZIPCODE_DATA, verb = 'post', session = s)

                    response = self._request(self.product_page_url, session = s, log_status_code = True)
                    if response.ok:
                        self.tree_html = html.fromstring(response.content)
                        if self.product_id:
                            self.price_data = self._request(self.PRICE_URL.format(self.product_id), session = s).json()

                        return

            except Exception as e:
                print traceback.format_exc(e)
                if self.lh:
                    self.lh.add_list_log('errors', str(e))

        self.is_timeout = True

    def not_a_product(self):
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        name = self.tree_html.xpath('//*[@id="productTitle"]/text()')
        return name[0] if name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _description(self):
        short_description = self.tree_html.xpath("//div[@aria-labelledby='pdDescription']/text()")
        return self._clean_text(short_description[0]) if short_description else None

    def _long_description(self):
        description = self.tree_html.xpath("//div[@aria-labelledby='pdDetails']/text()")
        return self._clean_text(description[0]) if description else None

    def _nutrition_facts(self):
        nutrition_facts = []
        nutrition_groups = self.tree_html.xpath('//div[@class="nutrition-table-header"]//table//tr')
        for nutrition_group in nutrition_groups:
            nutrition_key = nutrition_group.xpath('.//th/text()')
            nutrition_value = nutrition_group.xpath('.//td/text()')
            if nutrition_key and nutrition_value:
                nutrition_facts.append("%s: %s" % (nutrition_key[0], nutrition_value[0]))

        return nutrition_facts if nutrition_facts else None

    def _ingredients(self):
        ingredients = self.tree_html.xpath("//div[@aria-labelledby='pdIngredients']/text()")

        if ingredients:
            return [i.strip() for i in ingredients[0].split(',')]

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        images = self.tree_html.xpath('//div[contains(@class, "product-img")]//img/@src')

        if images:
            return ['https:' + i.strip() for i in images]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        if self.price_data:
            products_info = self.price_data.get('productsinfo')
            return products_info[0].get('price') if products_info else None

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        brand = self.tree_html.xpath("//div[@aria-labelledby='pdAboutProducer']//address/text()")
        return self._clean_text(brand[0]) if brand else None

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
        "title_seo" : _title_seo,
        "description" : _description,
        "long_description" : _long_description,
        "ingredients": _ingredients,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,

        # CONTAINER : SELLERS
        "price_amount" : _price_amount,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "brand" : _brand,
        }
