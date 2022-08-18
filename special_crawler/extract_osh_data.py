#!/usr/bin/python

import re

from lxml import html
from extract_data import Scraper

from product_ranking.guess_brand import guess_brand_from_first_words


class OshScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.osh.com/<product-name>"

    def check_url_format(self):
        m = re.match(r"^https?://www.osh.com/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if self.tree_html.xpath('//input[@id="variantProductcode"]'):
            return False
        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath('//input[@id="variantProductcode"]/@value')
        return product_id[0] if product_id else None


    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath('//div[@class="producttitle"]/span/text()')
        return product_name[0] if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        title_seo = self.tree_html.xpath('//title/text()')
        return self._clean_text(title_seo[0]) if title_seo else None

    def _sku(self):
        sku = self.tree_html.xpath('//h4[contains(text(), "Sku Number")]/following-sibling::p/text()')
        return sku[0] if sku else None

    def _description(self):
        description = self.tree_html.xpath('//h4[contains(text(), "Overview")]/following-sibling::p/text()')
        return description[0] if description else None

    def _features(self):
        features = self.tree_html.xpath('//h4[contains(text(),"Features")]/parent::div//li/text()')
        return [x.strip() for x in features] if features else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//img[@data-primaryimagesrc]/@data-primaryimagesrc')
        if image_urls:
            return ['http://www.osh.com' + x for x in image_urls if x != '']

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath('//div[@class="osh-price-label"]/h2/text()')
        return price[0] if price else None

    def _in_stores(self):
        in_store = self.tree_html.xpath('//span[contains(text(), "In Store")]')
        return int(bool(in_store))

    def _site_online(self):
        site_online = self.tree_html.xpath('//span[contains(text(), "Online")]')
        return int(bool(site_online))

    def _marketplace(self):
        return 0

    def _site_online_out_of_stock(self):
        online_availability = self.tree_html.xpath('//span[contains(text(), "Out of Stock Online")]')
        if online_availability:
            return 1
        return 0

    def _in_stores_out_of_stock(self):
        stores_availability = self.tree_html.xpath('//span[contains(text(), "Also Available In Store")]')
        if stores_availability:
            return 0
        return 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath('//div[@id="breadcrumb"]//a/text()')
        return [x.strip() for x in categories] if categories else None

    def _brand(self):
        return guess_brand_from_first_words(self._product_name())

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\r\n\t]", "", text).strip()

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
        "title_seo": _title_seo,
        "sku": _sku,
        "description": _description,
        "features": _features,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "marketplace": _marketplace,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
