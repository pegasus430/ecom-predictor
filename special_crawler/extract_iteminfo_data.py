#!/usr/bin/python

import re
import json
import traceback
import requests

from extract_data import Scraper
from lxml import html

class IteminfoScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://iteminfo.com/product/<product-id>"

    PRODUCT_URL = "http://iteminfo.com/GetProduct/{product_id}"

    REVIEW_URL = 'https://cdn.powerreviews.com/repos/15458/pr/pwr/content/{review_part}/contents.js'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = {}
        self.review_json = None

    def check_url_format(self):
        m = re.match(r"^https?://iteminfo.com/product/(\d+)$", self.product_page_url, re.I)
        if m:
            self.product_id = m.group(1)
        return bool(m)

    def _extract_page_tree(self):
        for i in range(self.MAX_RETRIES):
            try:
                product_url = self.PRODUCT_URL.format(product_id=self.product_id)
                response = requests.get(product_url, timeout=10).json()
                self.product_json = json.loads(response.get('Model', '{}'))
            except:
                print traceback.format_exc()

    def not_a_product(self):
        if not self.product_json:
            return True
        self._extract_review_json()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_review_json(self):
        try:
            product_model = self.product_json.get('ItemSummary', {}).get('Sku')
            review_part = self.get_review_url_part(product_model)
            url = self.REVIEW_URL.format(review_part=review_part)
            content = requests.get(url, timeout=20).content
            content = re.findall(r'\] = (.*?)};', content)
            review_json = json.loads(content[0] + '}')
            self.review_json = review_json.get('locales', {}).get('en_US')
        except:
            print traceback.format_exc()

    def get_review_url_part(self, product_model):
        """This method was created as copy of javascript function g(c4) from
        full.js. It will generate numerical part of url for reviews.
        example: 06/54 for url
        http://www.bjs.com/pwr/content/06/54/P_159308793-en_US-meta.js

        I use the same variables names as in js, but feel free to change them
        """
        c4 = product_model
        c3 = 0
        for letter in c4:
            c7 = ord(letter)
            c7 = c7 * abs(255 - c7)
            c3 += c7

        c3 = c3 % 1023
        c3 = str(c3)

        cz = 4
        c6 = list(c3)

        c2 = 0
        while c2 < (cz - len(c3)):
            c2 += 1
            c6.insert(0, "0")

        c3 = ''.join(c6)
        c3 = c3[0: 2] + '/' + c3[2: 4]
        return c3

    def _product_id(self):
        return self.product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.product_json.get('ItemSummary', {}).get('Title')

    def _product_title(self):
        return self._product_name()

    def _product_brand(self):
        brand = None
        index = None
        attr_list = None
        brand_by_html = None

        brand_by_json = self.product_json.get('Panels', {}).get('Datasheet')

        if brand_by_json:
            brand_by_html = html.fromstring(brand_by_json.encode('utf-8'))
        if brand_by_html:
            attr_list = brand_by_html.xpath("//td[@class='attr']/text()")
        if attr_list:
            for attr in attr_list:
                if 'brand name' in attr.lower():
                    index = attr_list.index(attr)
                    break
        if index:
            brand = brand_by_html.xpath(".//td[@class='attr-val']/text()")[index]
        return brand

    def _description(self):
        return self.product_json.get("Item", {}).get("Description")

    # ###########################################
    # ############### CONTAINER : PAGE_ATTRIBUTES
    # ###########################################

    def _image_urls(self):
        images = self.product_json.get('ResourceHelper', {}).get('CarouselImages', [])
        img_url = []
        for image in images:
            img_url.append(image[1]['Url'])

        return img_url if img_url else None

    # ##########################################
    # ############### CONTAINER : SELLERS
    # ##########################################

    def _price_amount(self):
        return self.product_json.get('ItemExtension', {}).get('Price')

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    # ##########################################
    # ############### CONTAINER : REVIEWS
    # ##########################################

    def _reviews(self):
        product_model = self.product_json.get('ItemSummary', {}).get('Sku')
        review_rating = []
        try:
            for key, item in self.review_json.iteritems():
                if product_model in key:
                    reviews = item.get('reviews')
                    self.review_count = int(reviews.get('review_count', '0'))
                    self.average_review = float(reviews.get('avg', '0.0'))

                    for i in range(0, 5):
                        ratingFound = False
                        for star, rating in enumerate(reviews.get('review_ratings', [])):
                            if star == i:
                                review_rating.append([star + 1, rating])
                                ratingFound = True
                                break

                        if not ratingFound:
                            review_rating.append([i + 1, 0])

        except:
            print traceback.format_exc()

        return review_rating[::-1] if review_rating else None

    # ##########################################
    # ############### CONTAINER : CLASSIFICATION
    # ##########################################

    def _categories(self):
        category_info = self.product_json.get('CategoryCrumbs', [])
        return [c.get('Name') for c in category_info]

    def _upc(self):
        return self.product_json.get("Item", {}).get("Skus", {}).get("UPC")

    def _sku(self):
        return self.product_json.get('ItemSummary', {}).get('Sku')

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,
        "reviews": _reviews,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "brand": _product_brand,
        "sku": _sku,
        "upc": _upc,
        "description": _description,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories
        }
