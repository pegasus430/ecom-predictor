#!/usr/bin/python

import re
from extract_data import Scraper
from lxml import html

class SanalmarketScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.sanalmarket.com.tr/kweb/prview/.*"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

    def check_url_format(self):
        m = re.match(r"^https?://www.sanalmarket.com.tr/kweb/prview/.*?", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[@class="uyeBilgiLinkLayout"]')) < 1:
            return True

        return False

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _brand(self):
        brand = self.tree_html.xpath('//input[@name="brand"]/@value')
        if brand:
            brand = brand[0]
        else:
            brand = re.search('brand = "(.*?)"', html.tostring(self.tree_html), re.DOTALL).group(1)
        return brand

    def _product_name(self):
        product_name = self.tree_html.xpath('//h1[@itemprop="name"]/text()')
        return product_name[0].strip()

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        description = self.tree_html.xpath('//div[@id="group0ProductDetail"]//text()')
        if description:
            return "".join(description)

    def _sku(self):
        sku = self.tree_html.xpath('//input[@name="sku"]/@value')
        return sku[0]

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//a[contains(@id,"zoom")]/@href')
        return image_urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath('//span[@itemprop="price"]/text()')
        price = price[0].replace(',', '.')
        return price + 'TL' if price else None

    def _price_currency(self):
        return 'TL'

    def _in_stores(self):
        return 1

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
        categories = self.tree_html.xpath('//ul[@class="titleNavList"]//span/text()')
        return [self._clean_text(category.replace('>', '')) for category in categories[:-1]]

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {

        # CONTAINER : PRODUCT_INFO
        "brand": _brand,
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo": _title_seo,
        "description": _description,
        "sku": _sku,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "price_currency": _price_currency,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,

        }
