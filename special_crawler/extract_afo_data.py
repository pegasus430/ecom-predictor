#!/usr/bin/python

import re
from extract_data import Scraper

class AfoScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is https://www.afo.com/.*"

    def check_url_format(self):
        m = re.match(r"^https://www.afo.com/.*$", self.product_page_url)
        return not not m

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def not_a_product(self):
        if not self.tree_html.xpath('//div[contains(@class, "product-view")]'):
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath('//input[@name="product"]/@value')
        if product_id:
            return product_id[0]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath('//div[contains(@class, "product-shop")]'
                                            '/div[contains(@class, "product-name")]'
                                            '/span/text()')
        if product_name:
            return product_name[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _model(self):
        model = self.tree_html.xpath('//div[contains(@class, "short-description")]'
                                     '/span[@class="h4"]/text()')
        if model:
            return re.search('(\d+)', model[0], re.DOTALL).group(1)

    def _description(self):
        short_description = self.tree_html.xpath('//div[contains(@class, "short-description")]'
                                                 '/div[contains(@class, "std")]/text()')
        if short_description:
            return short_description[0]

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//div[contains(@class, "product-image-gallery")]'
                                          '/img[contains(@data-zoom-image, "")]/@src')
        if image_urls:
            return image_urls[1:]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath('//div[contains(@class, "price-info")]'
                                     '//span[@class="regular-price"]'
                                     '/span[@class="price"]/text()')
        if price:
            return price[0]

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
        return self.tree_html.xpath('//div[contains(@class, "breadcrumbs")]/ul/li/a/text()')

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo": _title_seo,
        "model": _model,
        "description": _description,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        }
