#!/usr/bin/python

import re
import urlparse

from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words


class SuperamaScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is https://www.superama.com.mx/.*"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
            "passkey=ca00NLtrMkSnTddOCbktCnskwSV7OaQHCOTa3EZNMR2KE" \
            "&apiversion=5.5" \
            "&displaycode=19472-es_mx" \
            "&resource.q0=products" \
            "&filter.q0=id:eq:{}" \
            "&stats.q0=questions,reviews"

    def check_url_format(self):
        m = re.match(r"^https://www.superama.com.mx/.*$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[@id="detalleProductoContainer"]')) < 1:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath('//div[@class="detail-description-upc"]/span/text()')
        product_id = re.search('(\d+)', product_id[0], re.DOTALL).group(1)
        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//h2[@id="nombreProductoDetalle"]'
                                            '/text()')
        if product_name:
            return product_name[0].strip()

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        desc_array = self.tree_html.xpath('//div[@class="detail-description-content"]'
                                           '/p//text()')
        description = ''
        for desc in desc_array:
            description += desc.strip()

        return description

    def _brand(self):
        return guess_brand_from_first_words(self._product_name())

    def _ingredients(self):
        ingredients_list = self.tree_html.xpath('//div[contains(@class, "content__ingredientes")]'
                                                '/p/text()')
        ingredients = []
        for ingredient in ingredients_list[0].split(','):
            ingredients.append(ingredient.replace('.', '').strip())

        if ingredients:
            return ingredients


    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//div[@class="sp-wrap"]'
                                          '/a/@href')
        return [urlparse.urljoin(self.product_page_url, img) for img in image_urls]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath('//div[@class="detail-description-price"]'
                                     '/span/text()')
        if price:
            return price[0]

    def _price_currency(self):
        return 'MXN'

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        stock_status = re.search('"availability":"(.*?)"', html.tostring(self.tree_html), re.DOTALL).group(1)
        return not bool('InStock' in stock_status)

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath('//ol[@class="breadcrumb"]/li/a/text()')
        return [self._clean_text(category) for category in categories[:1]]

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
        "description": _description, \
        "brand": _brand, \
        "ingredients": _ingredients, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls, \

        # CONTAINER : SELLERS
        "price": _price, \
        "price_currency": _price_currency, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "marketplace": _marketplace, \

        # CONTAINER : CLASSIFICATION
        "categories": _categories, \
    }
