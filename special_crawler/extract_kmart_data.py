#!/usr/bin/python

import re
import requests
import traceback

from lxml import html, etree
from extract_data import Scraper


class KMartScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.kmart.com/.*"

    PRODUCT_URL = "http://www.kmart.com/content/pdp/config/products/v1/products/{}?site=kmart"

    REVIEW_URL = "http://www.kmart.com/content/pdp/ratings/single/search/Kmart/{}&targetType=product&limit=10&offset=0"

    PRICE_URL = "http://www.kmart.com/content/pdp/products/pricing/v2/get/price/display/json?ssin={}" \
                "&priceMatch=Y&memberType=G&urgencyDeal=Y&site=KMART"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = None
        self.reviews = None
        self.price = None

        self._set_proxy()

    def check_url_format(self):
        m = re.match(r"https?://www.kmart.com/.*", self.product_page_url)
        return bool(m)

    def _pre_scrape(self):
        self._extract_extra_json()

    def not_a_product(self):
        if not self.product_json:
            return True

        return False

    def _extract_page_tree(self):
        with requests.Session() as s:
            prod_id = self._product_id()
            for i in range(5):
                try:
                    product_json = self._request(self.PRODUCT_URL.format(prod_id), session=s, log_status_code=True).json()
                    self.product_json = product_json['data']['product']
                    if self.product_json:
                        break
                except Exception as e:
                    if self.lh:
                        self.lh.add_list_log('errors', str(e))

                    print traceback.format_exc()

    def _extract_extra_json(self):
        with requests.Session() as s:
            prod_id = self._product_id()
            try:
                reviews = self._request(self.REVIEW_URL.format(prod_id), session=s).json()
                self.reviews = reviews.get('data', {})
            except:
                print traceback.format_exc()

            headers = {
                'Host': 'www.kmart.com',
                'Accept': 'application/json',
                'AuthID': 'aA0NvvAIrVJY0vXTc99mQQ==',
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': self.product_page_url
            }

            try:
                self.price = self._request(self.PRICE_URL.format(prod_id), headers=headers, session=s).json()
            except:
                print traceback.format_exc()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        prod_id = re.findall(r'\/p-([^/?]*)', self.product_page_url)
        return prod_id[0] if prod_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.product_json.get('name')

    def _product_title(self):
        return self.product_json.get('seo', {}).get('title')

    def _title_seo(self):
        return self.product_json.get('seo', {}).get('title')

    def _model(self):
        return self.product_json.get('mfr', {}).get('modelNo')

    def _specs(self):
        specs = {}
        if self.product_json.get('specs'):
            rows = self.product_json['specs'][0]['attrs']
            for row in rows:
                specs[row.get('name')] = row.get('val')

        return specs if specs else None

    def _description(self):
        description = None
        descs = self.product_json.get('desc', [])
        for desc in descs:
            if desc.get('type') == 'S':
                description = desc.get('val')

        return description

    def _long_description(self):
        description = None
        descs = self.product_json.get('desc', [])
        for desc in descs:
            if desc.get('type') == 'L':
                description = desc.get('val')

        return description

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        imgs = self.product_json.get('assets', {}).get('imgs', [])
        if imgs:
            imgs = imgs[0].get('vals', [])
            imgs = [x['src'] for x in imgs]

        return imgs

    def _pdf_urls(self):
        pdfs = self.product_json.get('assets', {}).get('attachments', [])
        pdfs = [x['link']['attrs']['href'] for x in pdfs]

        return pdfs

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################
    def _average_review(self):
        average_review = self.reviews.get('overall_rating')
        if average_review:
            return float(average_review)

    def _review_count(self):
        return int(self.reviews.get('review_count', 0))
 
    def _reviews(self):
        if self._review_count() == 0:
            return None

        reviews = []
        buckets = self.reviews.get('overall_rating_breakdown', [])
        for x in buckets:
            if x.get('name') and x.get('count'):
                reviews.append([int(x.get('name')), int(x.get('count'))])

        return reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price_amount(self):
        price_block = self.price['priceDisplay']['response'][0]['finalPrice']['display']
        price = re.search(r'\d*\.\d+|\d+', price_block)
        if price:
            price = float(price.group(0))

            return price

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

    def _categories(self):
        cat = self.product_json['taxonomy']['web']['sites']['kmart']['hierarchies'][0]['specificHierarchy']
        cat = [x['name'] for x in cat]
        return cat

    def _brand(self):
        return self.product_json.get('brand', {}).get('name')

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
        "model" : _model,
        "specs" : _specs,
        "description" : _description,
        "long_description" : _long_description,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "pdf_urls" : _pdf_urls,

        # CONTAINER : REVIEWS
        "review_count" : _review_count,
        "average_review" : _average_review,
        "reviews" : _reviews,

        # CONTAINER : SELLERS
        "price_amount" : _price_amount,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand
    }
