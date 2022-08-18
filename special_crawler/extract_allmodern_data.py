#!/usr/bin/python

import re
import json
import time
import requests
import traceback
from lxml import html

from extract_wayfair_data import get_inventory_data

from extract_data import Scraper
from spiders_shared_code.wayfair_variants import WayfairVariants

from product_ranking.guess_brand import guess_brand_from_first_words


class AllmodernScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVENTORY_URL = "https://www.allmodern.com/a/inventory/load?_txid={}"

    SINGLE_PRODUCT_INVENTORY_URL = "https://www.allmodern.com/a/product/get_liteship_and_inventory_data?_txid={}"

    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)" \
                 "Chrome/64.0.3282.186 Safari/537.36"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self._av = WayfairVariants()
        self.product_json = {}

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries(use_session=True, save_session=True)
        # Get inventory data
        custom_headers = [
            {
                'key': 'content-type',
                'value': 'application/json; charset=UTF-8'
            }
        ]
        self.inventory_data = get_inventory_data(self, custom_headers=custom_headers)

    def not_a_product(self):
        if self.tree_html.xpath("//meta[@property='og:type' and contains(@content, 'product')]"):
            self._extract_product_json()
            self._av.setupCH(self.tree_html)
            return False
        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_product_json(self):
        try:
            self.product_json = self.tree_html.xpath('//script[@type="application/ld+json"]/text()')
            self.product_json = json.loads(self.product_json[0])
        except:
            print traceback.format_exc()

            if self.lh:
                self.lh.add_list_log('errors', str(e))

    def _product_id(self):
        return re.search('ProductId":"(.*?)"},', html.tostring(self.tree_html)).group(1)

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.product_json['name']

    def _upc(self):
        return self.tree_html.xpath("//meta[@property='og:upc']/@content")[0].strip()

    def _features(self):
        features = self.tree_html.xpath("//ul[@class='ProductOverviewInformation-list']/li/text()")
        return features if features else None

    def _description(self):
        return self.product_json['description']

    def _sku(self):
        sku = self.tree_html.xpath("//*[@name='sku']/@value")
        if sku:
            return sku[0]

    def _variants(self):
        if self.inventory_data:
            return self._av._variants(self.inventory_data)

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_list = []
        image_urls = self.tree_html.xpath("//ul[contains(@class, 'InertiaCarouselComponent')]"
                                          "/li//img[@class='ImageComponent-image']/@src")
        for image_url in image_urls:
            if image_url not in image_list:
                image_list.append(image_url)
        return image_list if image_list else None

    def _pdf_urls(self):
        pdf_links = self.tree_html.xpath("//a[contains(@href,'.pdf')]/@href")

        if pdf_links:
            return pdf_links

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        average_rating = self.tree_html.xpath('//meta[@itemprop="ratingValue"]/@content')
        if average_rating:
            return round(float(average_rating[0]), 1)

    def _review_count(self):
        review_count = re.search('"reviewCount":(\d+),', html.tostring(self.tree_html))

        if review_count:
            return int(review_count.group(1))

        return 0

    def _reviews(self):
        if self._review_count() > 0:
            rating_mark_list = self.tree_html.xpath('//div[@class="ProductReviewsHistogram-count"]/text()')
            rating_mark_list = [int(count) for count in rating_mark_list]
            rating_mark_list = [[5 - index, count] for index, count in enumerate(rating_mark_list)]

            return rating_mark_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        return '$' + str(self.product_json['offers']['price'])

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        stock = self.product_json.get('offers', {}).get('availability')

        if self.inventory_data and not stock:
            if isinstance(self.inventory_data, dict):
                return int(self.inventory_data.get('inventory', [{}])[0].get('available_quantity', 0) == 0)

        if 'instock' in stock.lower():
            return 0
        return 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//ol[contains(@class, 'Breadcrumbs-list')]"
                                          "/li/a/text()")

        return categories

    def _brand(self):
        brand = self.tree_html.xpath("//meta[@property='og:brand']/@content")
        if brand:
            return brand[0]
        return guess_brand_from_first_words(self._product_name())

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "upc": _upc,
        "features": _features,
        "description": _description,
        "sku": _sku,
        "image_urls": _image_urls,
        "variants": _variants,

        # CONTAINER : REVIEWS
        "review_count": _review_count,
        "average_review": _average_review,
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
    }
