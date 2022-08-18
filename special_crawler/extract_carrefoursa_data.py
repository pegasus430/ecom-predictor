#!/usr/bin/python

import re
from urlparse import urljoin
from extract_data import Scraper
from lxml import html

class CarrefourSaScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.carrefoursa.com/tr/.*"

    def check_url_format(self):
        m = re.match(r"https?://www.carrefoursa.com/tr/.*", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        canonical_link = self.tree_html.xpath("//link[@rel='canonical']/@href")
        if canonical_link:
            product_id =canonical_link[0].split("p-")
        return product_id[-1] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        title = self.tree_html.xpath('//div[contains(@class, "product-details")]'
                                     '//div[contains(@class, "name")]//h1/text()')
        return self._clean_text(title[0]) if title else None

    def _brand(self):
        brand = self.tree_html.xpath('//div[contains(@class, "product-details")]'
                                     '//div[contains(@class, "brand")]//a/text()')
        return self._clean_text(brand[0]) if brand else None

    def _product_title(self):
        return self._product_name()

    def _long_description(self):
        description = self.tree_html.xpath('//div[@class="tab-details"]//span/text()')
        return description[1].encode('utf-8') if description else None


    def _description(self):
        long_description = self.tree_html.xpath('//meta[@name="description"]/@content')
        return self._clean_text(long_description[0]) if long_description else None

    def _average_review(self):
        review_info = self.tree_html.xpath('//div[contains(@class, "rating")]/@data-rating')
        if review_info:
            average_review = re.findall('(\d*\.\d+)', review_info[0])
        return float(average_review[0]) if average_review else None

    def _review_count(self):
        reviews_count = self.tree_html.xpath('//span[contains(@class, "reviewsNumber")]//text()')
        if reviews_count:
            reviews_count = re.findall('(\d+)', reviews_count[0])
            return float(reviews_count[0]) if reviews_count else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        img_urls =img_urls = self.tree_html.xpath('//div[@class="thumb-images"]//img[@class="lazyOwl"]/@data-src')
        if not img_urls:
            img_urls = self.tree_html.xpath('//div[@class="thumb"]//img[@class="lazyOwl"]/@data-src')
            img_urls = [urljoin(self.product_page_url, img_url) for img_url in img_urls]
        return img_urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price_info = self.tree_html.xpath('//div[contains(@class, "price-row")]'
                                          '//span[contains(@class, "item-price")]/text()')
        price = re.search(r'(\d*\.\d+|\d+)', price_info[0].replace(',','.'), re.DOTALL)
        return float(price.group()) if price else None

    def _price_currency(self):
        return "TL"

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath('//ol[@class="breadcrumb"]//li/a/text()')
        return categories if categories else None

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "long_description": _long_description,
        "description": _description,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "average_review": _average_review,
        "review_count": _review_count,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "price_currency": _price_currency,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
