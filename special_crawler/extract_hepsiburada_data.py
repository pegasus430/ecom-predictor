# -*- coding: utf-8 -*-
#!/usr/bin/python

import re
import json
import traceback

from lxml import html
from extract_data import Scraper
from spiders_shared_code.hepsiburada_variants import HepsiburadaVariants


class HepsiburadaScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.hepsiburada.com/*"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.hv = HepsiburadaVariants()

    def check_url_format(self):
        m = re.match(r"https?://www.hepsiburada.com/.*", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        self.product_json = self._product_json()
        if not self.product_json:
            return True
        variants = self.product_json.get('variants', [])
        self.hv.setupCH(variants, self._sku())
        return False

    def _product_json(self):
        product_json = self._find_between(html.tostring(self.tree_html), 'var productModel = ', '};')
        try:
            product_json = json.loads(product_json + '}')
            return product_json.get('product')
        except:
            print traceback.format_exc()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.product_json.get('productId')

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.product_json.get('name')

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _description(self):
        description = self.product_json.get('description')
        return self._clean_text(description)

    def _sku(self):
        return self.product_json.get('sku')

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.product_json.get('allImages', [])
        image_urls = [i.get('url') for i in image_urls if i.get('url')]
        return image_urls

    def _video_urls(self):
        return [self.product_json.get('video', {}).get('link')]

    def _variants(self):
        return self.hv._variants()

    def _price_amount(self):
        price = self.tree_html.xpath('//span[@itemprop="price"]/@content')
        return float(price[0]) if price else None

    def _price_currency(self):
        price_currency = self.tree_html.xpath('//span[@itemprop="priceCurrency"]/@content')
        return price_currency[0] if price_currency else 'TRY'

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        average_review = self.product_json.get('ratingStar', '').replace(',', '.')
        try:
            self.average_review = float(average_review)
        except:
            print traceback.format_exc()
            self.average_review = None
        return self.average_review

    def _review_count(self):
        self.review_count = self.product_json.get('totalReviewsCount')
        return self.review_count

    def _reviews(self):
        reviews = self.tree_html.xpath('//span[@class="rating-count"]/text()')
        review_list = [[5, 0], [4, 0], [3, 0], [2, 0], [1, 0]]
        for idx, review in enumerate(reviews):
            rating_count = re.search(r'(\d+)', review)
            if rating_count:
                rating_count = int(rating_count.group(1))
                review_list[idx][1] = rating_count
        self.reviews = review_list
        return self.reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 1 \
            if not self.product_json.get('currentListing', {}).get('stockInformation', {}).get('isInStock', False) \
            else 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = [i.get('breadcrumbTitle') for i in self.product_json.get('categories', []) if i.get('breadcrumbTitle')]
        return categories

    def _brand(self):
        return self.product_json.get('brand')

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        "product_id": _product_id,
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "description": _description,
        "sku": _sku,
        "variants": _variants,
        "image_urls": _image_urls,
        "video_urls": _video_urls,
        "review_count": _review_count,
        "average_review": _average_review,
        "reviews": _reviews,
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "brand": _brand,
        "categories": _categories,
        }
