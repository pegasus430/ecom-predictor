#!/usr/bin/python

import re
import json
import traceback
from lxml import html

from extract_data import Scraper
from spiders_shared_code.nordstrom_variants import NordStromVariants


class NordStromScraper(Scraper):

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://shop.nordstrom.com/s/<prod-name>/<prod-id>"

    REVIEW_URL = "http://nordstrom.ugc.bazaarvoice.com/4094redes/{}/reviews.djs?format=embeddedhtml"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.product_json = None
        self.nv = NordStromVariants()

    def check_url_format(self):
        m = re.match("https?://shop\.nordstrom\.com/s/[a-z0-9\-]+/\d+", self.product_page_url)
        return bool(m)

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def _product_json(self):
        try:
            product_json = self._find_between(html.tostring(self.tree_html), '(ProductDesktop, ', '), document.')
            product_json = json.loads(product_json)
            self.product_json = product_json.get('initialData', {})
            self.nv.setupCH(self.product_json)
        except:
            print 'Error Parsing Product Json: {}'.format(traceback.format_exc())

    def not_a_product(self):
        self._product_json()
        if self.product_json:
            if self.product_json.get('Type') == 'Products':
                return False
        return True

    def _product_id(self):
        return self.product_json.get('Model', {}).get('StyleModel', {}).get('Id')

    def _product_name(self):
        return self.product_json.get('Model', {}).get('StyleModel', {}).get('Name')

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        return self.product_json.get('Model', {}).get('StyleModel', {}).get('Description')

    def _image_urls(self):
        image_urls = []
        for image_url in self.product_json.get('Model', {}).get('StyleModel', {}).get('StyleMedia', []):
            if image_url.get('IsDefault'):
                image_urls.append(image_url.get('ImageMediaUri', {}).get('Large'))
        return image_urls

    def _price(self):
        return self.product_json.get('Model', {}).get('StyleModel', {}).get('Price').get('CurrentPrice')

    def _price_currency(self):
        return self.product_json.get('Model', {}).get('StyleModel', {}).get('Price').get('CurrencyCode')

    def _variants(self):
        return self.nv._variants()

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0 if self.product_json.get('Model', {}).get('StyleModel', {}).get('IsAvailable') else 1

    def _in_store_only(self):
        return 1 if self.product_json.get('Model', {}).get('StyleModel', {}).get('IsInStoreOnlyBridal') else 0

    def _categories(self):
        categories = []
        for category in self.product_json.get('Breadcrumbs', []):
            if category.get('Id') != 0:
                categories.append(category.get('Text'))
        return categories

    def _brand(self):
        return self.product_json.get('Model', {}).get('StyleModel', {}).get('Brand', {}).get('Name')

    def _model(self):
        return self.product_json.get('Model', {}).get('StyleModel', {}).get('Number')

    def _reviews(self):
        if self.is_review_checked:
            return self.reviews
        self.is_review_checked = True
        review_list = [[5, 0], [4, 0], [3, 0], [2, 0], [1, 0]]
        review_id = self.product_json.get('Model', {}).get('StyleModel', {}).get('BazaarvoiceStyleId')
        review_url = self.REVIEW_URL.format(review_id)
        content = self._request(review_url).text
        review_count = re.findall(r'\\"BVRRNumber\\">(\d+)<\\/span>', content)
        if review_count:
            self.review_count = int(review_count[0])
            average_review = re.findall(r'BVRRRatingNumber\\">(.*?)<\\/span>', content)
            if average_review:
                self.average_review = float(average_review[0])
            reviews = re.findall(r'(\d+) review\(s\)', content)
            for idx, review in enumerate(reviews):
                review_list[idx][1] = int(review)
            self.reviews = review_list
        return self.reviews


    DATA_TYPES = { \
        "product_id" : _product_id, \

        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "description" : _description, \

        "image_urls" : _image_urls, \

        # "reviews": _reviews, \
        "variants": _variants, \

        "price" : _price, \
        "price_currency" : _price_currency, \
        "site_online": _site_online, \
        "in_stores" : _in_stores, \
        "site_online_out_of_stock": _site_online_out_of_stock, \

        "categories" : _categories, \
        "brand" : _brand, \
        "model" : _model,
        }
