#!/usr/bin/python

import re
import json
import traceback

from lxml import html
from extract_data import Scraper
from spiders_shared_code.nike_variants import NikeVariants


class NikeScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://store.nike.com/us/en_us/pd/<product-name>/<product-id>"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = None
        self.nv = NikeVariants()

        self._set_proxy()

    def check_url_format(self):
        m = re.match(r"^https?://store.nike.com/.*$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')[0].strip()

        if itemtype != "product":
            return True

        self._extract_product_json()
        self.nv.setupCH(self.tree_html)

        return False

    def _extract_product_json(self):
        product_json = self._find_between(html.tostring(self.tree_html), '"template-data">', '</script>')

        try:
            self.product_json = json.loads(product_json)
        except Exception as e:
            print traceback.format_exc(e)

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath("//input[@name='productId']/@value")
        return product_id[0].strip() if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self._product_title()

    def _product_title(self):
        product_title = self.tree_html.xpath("//title/text()")
        if product_title:
            product_title = product_title[0].replace("Nike.com", "").strip()

        return product_title

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        description = self.tree_html.xpath("//div[@class='pi-pdpmainbody']//p/text()")
        description = self._clean_text(" ".join(description))

        return description

    def _long_description(self):
        long_description = self.tree_html.xpath("//div[@class='pi-pdpmainbody']//li")
        long_description = map(html.tostring, long_description)

        return self._clean_text(" ".join(long_description))


    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath("//ul[@class='exp-pdp-alt-images-carousel']//li//img/@data-large-image")

        return image_urls if image_urls else None

    def _variants(self):
        return self.nv._variants()

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        return self.product_json.get('reviews', {}).get('formattedAverageRating')

    def _review_count(self):
        review_count = 0
        try:
            review_count = int(self.product_json.get('reviews', {}).get('totalReviewCount', 0))
        except Exception as e:
            print traceback.format_exc(e)

        return review_count

    def _reviews(self):
        ratings_distribution = []
        try:
            ratings_distribution = self.product_json.get('reviews', [])\
                .get('reviewStatistics', [])\
                .get('ratingDistribution', [])
        except Exception as e:
            print traceback.format_exc(e)

        reviews = [[1, 0], [2, 0], [3, 0], [4, 0], [5, 0]]

        for rating in ratings_distribution:
            try:
                reviews[int(rating['ratingValue']) - 1][1] = rating['count']
            except Exception as e:
                print traceback.format_exc(e)

        return reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//span[contains(@class, 'exp-pdp-local-price')]/text()")
        return price[0].strip() if price else None

    def _price_currency(self):
        return 'USD'

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
        return "NIKE"

    def _sku(self):
        return self._product_id()

    def _categories(self):
        categories = []
        categories.append(self.product_json.get('trackingData').get('product').get('category'))

        return categories if categories else None

    ##########################################
    ################ HELPER BLOCK
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id, \

        # CONTAINER : PRODUCT_INFO
        "title_seo": _title_seo, \
        "product_name": _product_name, \
        "product_title": _product_title, \
        "sku": _sku, \
        "description": _description, \
        "long_description": _long_description, \
        "variants" : _variants, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls, \

        # CONTAINER : REVIEWS
        "review_count": _review_count, \
        "average_review": _average_review, \
        "reviews": _reviews, \

        # CONTAINER : SELLERS
        "price": _price, \
        "price_currency": _price_currency, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "in_stores_out_of_stock": _in_stores_out_of_stock, \

        # CONTAINER : CLASSIFICATION
        "brand": _brand, \
        "categories": _categories, \
        }
