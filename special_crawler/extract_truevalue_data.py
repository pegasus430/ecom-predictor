#!/usr/bin/python

import re
from lxml import html
from extract_data import Scraper
from HTMLParser import HTMLParser


class TruevalueScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.truevalue.com/.*"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
            "passkey=p5zfp3g4eesutulj5jftp1i68" \
            "&apiversion=5.5" \
            "&displaycode=9048-en_us" \
            "&resource.q0=products" \
            "&filter.q0=id:eq:{}" \
            "&stats.q0=reviews"


    def check_url_format(self):
        m = re.match(r"^https?://www.truevalue.com/.*$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[contains(@id, "mainProductImg")]')) < 1:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = re.search("productId=(\d+)", html.tostring(self.tree_html)).group(1)
        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//h1[@class="product-name"]/text()')
        if product_name:
            return HTMLParser().unescape(product_name[0].strip())

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        short_description = self.tree_html.xpath('//div[@class="pdp-container"]'
                                                 '/p/text()')
        return short_description

    def _item_num(self):
        item_num = self.tree_html.xpath('//span[@class="style-number"]'
                                        '/text()')
        if item_num:
            item_num = re.search('(\d+)', item_num[0], re.DOTALL).group(1)
            return item_num

    def _brand(self):
        brand = self.tree_html.xpath('//span[@class="manufacturer-name"]'
                                     '/text()')
        return brand if brand else None

    def _model(self):
        model_num = self.tree_html.xpath('//span[@class="model-number"]'
                                        '/text()')
        if model_num:
            item_num = re.search('(\d+)', model_num[0], re.DOTALL).group(1)
            return item_num

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//div[@id="more-images"]'
                                          '//a/@href')
        if not image_urls:
            image_urls = self.tree_html.xpath('//div[@id="mainProductImg"]'
                                          '/img/@src')
        return image_urls if image_urls else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath('//div[@id="priceContainer"]//div[@class="price"]/text()')
        if price:
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
        categories = self.tree_html.xpath('//div[@class="breadcrumb-container"]//div[contains(@class, "crumb")]/a/text()')
        for category in categories:
            if category.strip():
                category_list.append(category.strip())

        return category_list

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
        "item_num": _item_num, \
        "brand": _brand, \
        "model": _model, \
 \
        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls, \

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
