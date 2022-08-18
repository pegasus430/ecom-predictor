#!/usr/bin/python

import re
import traceback

from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words


class FrysScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://(www.)frys.com/product/*"

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def check_url_format(self):
        m = re.match("https?://(www\.)?frys\.com/product/.*", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')

        if itemtype and itemtype[0].strip() == 'product':
            return False

        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath(
            '//div[@class="product-label-list"]//span[@class="product-label-value"]/text()')
        return product_id[0].strip() if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath('//*[@class="product-title"]//strong/text()')

        return self._clean_text(product_name[0]) if product_name else None

    def _product_title(self):
        product_title = self.tree_html.xpath("//meta[@property='og:title']/@content")

        return self._clean_text(product_title[0]) if product_title else None

    def _model(self):
        rows = self.tree_html.xpath(
            '//div[@class="product-label-list"]//span[@class="product-label"]')

        for r in rows:
            row_title = r.xpath('.//span[@class="product-label-title"]/text()')
            row_value = r.xpath('.//span[@class="product-label-value"]/text()')
            if row_title and row_value and 'Model:' in row_title[0]:
                return row_value[0].strip()

    def _features(self):
        feature_rows = self.tree_html.xpath("//div[@id='#specifications']//table//tr")
        features = []

        for feature_row in feature_rows:
            feature_group = feature_row.xpath(".//td/text()")
            try:
                feature_title = feature_group[0].strip()
                feature_value = feature_group[1].strip()
                features.append(feature_title + ' ' + feature_value)
            except Exception as e:
                print traceback.format_exc(e)

        if features:
            return features

    def _description(self):
        description = self.tree_html.xpath("//div[@id='features']/descendant::text()")
        description = self._clean_text(','.join(description))

        return description if description else None

    def _long_description(self):
        long_description = self.tree_html.xpath("//div[@id='features']//ul")
        if long_description:
            long_description = self._clean_text(html.tostring(long_description[0]))

        return long_description

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath(
            "//div[@class='slider-for']//div[@class='slider-image-box']//img/@src")

        return image_urls if image_urls else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//*[@id='did_price1valuediv']/text()")

        return price[0].strip() if price else None

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        stock_info = self.tree_html.xpath("//div[@class='product_special_icons']//font/text()")
        if stock_info and 'out of stock' in stock_info[0].lower():
            return 1

        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath(
            "//ul[contains(@class, 'frys-breadcrumb')]//li[@class='frys-b-item']//a/text()")

        categories = map(self._clean_text, categories)
        categories = map(lambda x: re.sub(r'\xbb', '', x), categories)

        return categories[1:] if categories else None

    def _brand(self):
        attributes = self.tree_html.xpath("//div[@id='ProductAttributes']//text()")
        brand = None

        for attribute in attributes:
            if "Manufacturer" in attribute:
                brand = attribute.replace("Manufacturer", "").strip()
                brand = brand.replace(": ", "")

        if brand:
            return brand

        return guess_brand_from_first_words(self._product_name())

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "features" : _features,
        "description" : _description,
        "model" : _model,
        "long_description" : _long_description,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,

        # CONTAINER : SELLERS
        "price" : _price,
        "in_stores" : _in_stores,
        "site_online" : _site_online,
        "site_online_out_of_stock" : _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
