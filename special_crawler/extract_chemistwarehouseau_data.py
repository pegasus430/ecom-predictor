#!/usr/bin/python

import re
from lxml import html

from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words

class ChemistwarehouseauScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.chemistwarehouse.com.au/buy/<product_id>/<product_name>"

    REVIEW_URL = "http://api.bazaarvoice.com/data/batch.json?" \
                 "passkey=5tt906fltx756rwlt29pls49v&apiversion=5.5&" \
                 "displaycode=13773-en_au&resource.q0=products&" \
                 "filter.q0=id:eq:{}&" \
                 "stats.q0=reviews&" \
                 "filteredstats.q0=reviews&" \
                 "filter_questions.q0=contentlocale:eq:en_US&" \
                 "filter_answers.q0=contentlocale:eq:en_US&" \
                 "filter_reviews.q0=contentlocale:eq:en_US&" \
                 "filter_reviewcomments.q0=contentlocale:eq:en_US"

    def check_url_format(self):
        m = re.match(r"^http://www.chemistwarehouse.com.au/buy/\d+/[\w-]+$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        type = re.findall(r'"ecomm_pagetype": "(.*?)",', html.tostring(self.tree_html))
        return type[0] != 'Product' if type else True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _product_id(self):
        product_id = re.findall(r'"ecomm_prodid": "(.*?)",', html.tostring(self.tree_html))
        return product_id[0] if product_id else None

    def _sku(self):
        return self._product_id()

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath('//div[@itemprop="name"]/h1/text()')
        return product_name[0] if product_name else None

    def _brand(self):
        title = self._product_name()
        return guess_brand_from_first_words(title) if title else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _description(self):
        description = self.tree_html.xpath('//*[@class="product-info-container"]')
        return html.tostring(description[0]) if description else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _image_urls(self):
        img_urls = self.tree_html.xpath('//img[@itemprop="image"]/@src2')
        return img_urls if img_urls else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath('//div[@itemprop="price"]/text()')
        return price[0] if price else None

    def _price_amount(self):
        price = self._price()
        return float(price.replace(',', '')[1:]) if price else 0

    def _price_currency(self):
        return "AUD"

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
        categories = self.tree_html.xpath('//div[@class="breadcrumbs"]/a/text()')
        return categories[1:] if categories else None

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id": _product_id, \
 \
        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name, \
        "product_title": _product_title, \
        "title_seo": _title_seo, \
        "sku": _sku, \
        "description" : _description, \
 \
        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls, \
 \
        # CONTAINER : SELLERS
        "price": _price, \
        "price_amount": _price_amount, \
        "price_currency": _price_currency, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        'in_stores_out_of_stock': _in_stores_out_of_stock, \
 \
        # CONTAINER : CLASSIFICATION
        "categories": _categories, \
        "brand": _brand, \
        }
