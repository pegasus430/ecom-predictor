#!/usr/bin/python

import re
from HTMLParser import HTMLParser
from product_ranking.guess_brand import guess_brand_from_first_words
from extract_data import Scraper
from lxml import html


class GiantEagleScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.gianteagle.com/.*"

    def check_url_format(self):
        m = re.match(r"^https?://www.gianteagle.com/.*$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[@id="productDetails"]')) < 1:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _product_id(self):
        product_id = self.tree_html.xpath('//div[@id="productDetails"]/@data-prodid')
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath('//div[@id="contentContainer"]'
                                            '/div/h1/text()')
        if product_name:
            return HTMLParser().unescape(product_name[0])

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        short_description = self.tree_html.xpath('//div[@class="productDescriptionBottom"]'
                                                 '/p/text()')
        if short_description:
            short_description = [i.strip() for i in short_description]
            return " ".join(short_description)

    def _ingredients(self):
        ingredients = self.tree_html.xpath('//div[@class="tabsWrapper"]'
                                           '/div/div/text()')
        if ingredients:
            return [i.strip() for i in ingredients[0].split(',')]

    def _brand(self):
        brand = self.tree_html.xpath('//span[@itemprop="brand"]/text()')
        if brand:
            return brand[0]
        return guess_brand_from_first_words(self._product_name())

    def _upc(self):
        upc = re.search('UPC/PLU: (\d+)', html.tostring(self.tree_html))
        if upc:
            return upc.group(1)

    def _nutrition_facts(self):
        nutrition_list = self.tree_html.xpath('//div[@class="nutrientGroupNutrients"]'
                                              '/div[@class="nutrient"]')[1:]
        nutrition_string_list = []
        for nutrition in nutrition_list:
            nutrition = nutrition.xpath('.//div/text()')
            nutrition = [i.strip() for i in nutrition]
            nutrition = " ".join(nutrition)
            nutrition_string_list.append(nutrition)

        return nutrition_string_list

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_list = []
        image_urls = self.tree_html.xpath('//div[@id="contentContainer"]'
                                          '//div[contains(@class, "productImage")]'
                                          '/img/@src')
        for image_url in image_urls:
            image_url = 'https://www.gianteagle.com' + image_url
            image_list.append(image_url)
        return image_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories_sel = self.tree_html.xpath('//ol[@id="breadcrumbs"]/li/a/text()')
        return [i.strip() for i in categories_sel]

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo": _title_seo,
        "description": _description,
        "upc": _upc,
        "nutrition_facts": _nutrition_facts,
        "ingredients": _ingredients,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "in_stores": _in_stores,
        "site_online": _site_online,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
    }
