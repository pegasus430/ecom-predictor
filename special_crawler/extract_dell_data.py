#!/usr/bin/python

import re
from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words
import requests


class DellScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.dell.com/.*"
    REVIEW_URL = "http://www.dell.com/csbapi/RatingDetails?ProductCode={product_id}"
    HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/58.0.3029.96 Safari/537.36"}

    def __init__(self, **kwargs):  # **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.reviews_checked = False

    def check_url_format(self):
        m = re.match(r"^http://www.dell.com/.*$", self.product_page_url)
        return not not bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[contains(@id, "product-details")]')) < 1:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath('//meta[@name="ProductId"]/@content')
        if product_id:
            return product_id[0]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath('//section[contains(@id, "page-title")]'
                                            '//h1[contains(@class, "Title")]/text()')
        if product_name:
            return product_name[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _mpn(self):
        mpn = re.search('data-mpn="(.*?)"', html.tostring(self.tree_html), re.DOTALL)
        if mpn:
            return mpn.group(1)

    def _description(self):
        short_description = self.tree_html.xpath('//meta[@name="DESCRIPTION"]'
                                                 '/@content')
        if short_description:
            return short_description[0]

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath("//div[@class='wc-gallery-thumb']//img/@src")
        if not image_urls:
            image_urls = self.tree_html.xpath('//ul[contains(@class, "slides")]'
                                              '/li/img[@class="carImg"]/@data-blzsrc')
        if not image_urls:
            image_urls = self.tree_html.xpath('//li/img[@data-testid="sharedPolarisHeroPdImage"]/@src')
        if not image_urls:
            image_urls = self.tree_html.xpath('//meta[@name="og:image"]/@content')
        if image_urls:
            return image_urls
    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        if self.reviews_checked:
            return self.reviews

        self.reviews_checked = True

        url = self.REVIEW_URL.format(product_id=self._product_id())
        data = requests.get(url=url, headers=self.HEADERS, timeout=10).json()

        self.review_count = data['Summary']['ReviewCountValue']
        self.average_review = round(float(data['Summary']['OverallRatingAverageValue']), 1)

        ratings = data['Summary']['RatingBreakdown']

        rating_mark_list = []
        values = ['OneStarCountValue', 'TwoStarCountValue', 'ThreeStarCountValue', 'FourStarCountValue',
                  'FiveStarCountValue']
        for i, v in enumerate(values):
            rating_mark_list.append([i+1, ratings[v]])

        self.reviews = rating_mark_list

        return self.reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath('//span[@data-testid="sharedPSPDellPrice"]/text()')
        if not price:
            price = self.tree_html.xpath('//span[@id="starting-price"]/text()')
        return price[0]

    def _price_amount(self):
        price = self._price()
        return float(price.replace('$', '').replace(',', ''))

    def _price_currency(self):
        return '$'

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
        return self.tree_html.xpath('//ol[contains(@class, "breadcrumb")]/li/a/text()')

    def _brand(self):
        brand = re.search('data-module-brand="(.*?)"', html.tostring(self.tree_html), re.DOTALL)
        if brand:
            return brand.group(1)
        return guess_brand_from_first_words(self._product_name())

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id": _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo": _title_seo, \
        "mpn": _mpn, \
        "description": _description, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls, \

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
        "brand": _brand, \
    }
