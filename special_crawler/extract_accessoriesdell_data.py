#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import requests

from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words
from HTMLParser import HTMLParser
from lxml import html


class AccessoriesDellScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://accessories.dell.com/.*"

    REVIEW_URL = "http://reviews.dell.com/2341-en_ca_ng/{id}/reviews.htm?format=embedded"

    def check_url_format(self):
        m = re.match(r"^https?://accessories.dell.com/.*$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[@id="maincontentcnt"]')) < 1:
            return True

        return False

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath('//span[@itemprop="name"]/text()')
        if product_name:
            return HTMLParser().unescape(product_name[0])

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        short_description = self.tree_html.xpath('//td[@class="LongDescription_width"]/span/div/text()')
        return short_description

    def _brand(self):
        return guess_brand_from_first_words(self._product_name())

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_list = []
        image_urls = self.tree_html.xpath('//a[contains(@onclick, "expandImageRotate") and contains(@onmouseover, "DisplayImage")]/@onclick')
        for image_url in image_urls:
            image_list.append(re.search('http(.*).jpg', image_url, re.DOTALL).group())
        return image_list

    def _manufacturer(self):
        manufacturer = re.search('Manufacturer Part# :(.*?)Dell', html.tostring(self.tree_html), re.DOTALL).group(1)
        return manufacturer.replace('|', '').strip() if manufacturer else None

    def _sku(self):
        sku = re.search('sku=(.*?)]', html.tostring(self.tree_html), re.DOTALL).group(1)
        return sku if sku else None

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################
    def _reviews(self):
        if self.is_review_checked:
            return self.reviews

        self.is_review_checked = True

        id = re.search('sku=(.*?)&', self.product_page_url, re.DOTALL)

        try:
            data = requests.get(self.REVIEW_URL.format(id=id.group(1)), timeout=10).text
            data = html.fromstring(data)
            average_review = data.xpath('//span[@itemprop="aggregateRating"]/span/text()')
            review_count = data.xpath('//meta[@itemprop="reviewCount"]/@content')
            self.average_review = average_review[0] if average_review else None
            self.review_count = review_count[0] if review_count else None

            review_list = []

            data = data.xpath('//div[@id="BVRRRatingSummarySourceID"]//div[contains(@class, "BVRRHistogramBarRow")]')
            for i in range(1, 6):
                rating_count = data[i-1].xpath('.//span[@class="BVRRHistAbsLabel"]/text()')
                review_list.append([6 - i, int(rating_count[0]) if rating_count else 0])
        except:
            return []
        self.reviews = review_list
        return self.reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath('//span[@name="pricing_sale_price"]/text()')
        if not price:
            price = self.tree_html.xpath('//span[@name="pricing_retail_price"]/text()')
        return price[0]

    def _price_amount(self):
        price = self._price()
        price = re.search('\d+\.?\d+', price).group()
        return float(price)

    def _price_currency(self):
        price = self._price()
        if '$' in price:
            return 'USD'

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        category_list = []
        categories = self.tree_html.xpath('//a[@class="lnk_crumb43"]/text()')
        for category in categories:
            if category.strip() and not category.strip() == '>':
                category_list.append(category.strip())

        return category_list

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo": _title_seo, \
        "description": _description, \
        "brand": _brand, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls, \
        "manufacturer": _manufacturer,
        "sku": _sku,

        # CONTAINER : REVIEWS
        "reviews": _reviews, \

        # CONTAINER : SELLERS
        "price": _price, \
        "price_amount": _price_amount, \
        "price_currency": _price_currency, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "marketplace": _marketplace, \

        # CONTAINER : CLASSIFICATION
        "categories": _categories, \
        }