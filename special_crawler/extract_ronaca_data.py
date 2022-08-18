#!/usr/bin/python

import re
import urlparse
import traceback

from lxml import html
from extract_data import Scraper

class RonacaScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.rona.ca/(en or fr)<product-name>"

    def check_url_format(self):
        m = re.match(r"^https?://www.rona.ca/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')
        if itemtype and itemtype[0] == 'product':
            return False
        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self._sku()

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[@itemprop='name']/text()")
        return product_name[0] if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _sku(self):
        sku = self.tree_html.xpath("//meta[@itemprop='sku']/@content")
        return sku[0] if sku else None

    def _model(self):
        articles = self.tree_html.xpath("//div[@class='article']//span/text()")
        for article in articles:
            if 'model' in article.lower():
                model = re.search('Model (.*)', article).group(1)
                break
        return model if model else None

    def _description(self):
        description = self.tree_html.xpath("//span[@class='textDescription']/text()")
        return description[0] if description else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []
        images = self.tree_html.xpath("//div[@class='zoomedImg']//img/@src")
        if images:
            for image in images:
                image_urls.append(urlparse.urljoin(self.product_page_url, image))
        return image_urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price_amount = None
        price_info = self.tree_html.xpath("//div[contains(@class, 'priceTop')]/ul/li[contains(@class, 'priceColumn')]"
                                     "//span[contains(@class, 'product_price large')]"
                                     "/span[@class='product_price_amount']//span/text()")
        if price_info:
            price_amount = re.search('\d+\.?\d*', ''.join(price_info).replace(',', '.'))
        return float(price_amount.group()) if price_amount else None

    def _price_currency(self):
        return 'CAD'

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//div[@id='breadcrumb']//a/text()")
        return categories[1:] if categories else None

    def _brand(self):
        brand = self.tree_html.xpath("//span[@itemprop='brand']/text()")
        return brand[0] if brand else None

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "sku": _sku,
        "model": _model,
        "description": _description,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "price_currency": _price_currency,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand
        }
