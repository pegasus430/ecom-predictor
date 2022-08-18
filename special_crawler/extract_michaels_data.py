#!/usr/bin/python

import re
import json

from lxml import html
from extract_data import Scraper


class MichaelsScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.michaels.com/<product-name>/<product id>.html"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
            "passkey=artgqo0gyla0epe3aypxybrs5" \
            "&apiversion=5.5" \
            "&displaycode=9022-en_us" \
            "&resource.q0=products" \
            "&filter.q0=id:eq:{}" \
            "&stats.q0=reviews"

    def check_url_format(self):
        m = re.match(r"^http://www.michaels.com/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')[0].strip()

        if itemtype != "product":
            return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = re.search('productId = (.*?),', html.tostring(self.tree_html))
        if product_id:
            product_id = product_id.group(1).replace('"', '')

        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[contains(@class, 'product-name')]/text()")

        return product_name[0].strip() if product_name else None

    def _product_title(self):
        return self._product_name()

    def _model(self):
        return self._product_id()

    def _description(self):
        short_description = self.tree_html.xpath("//div[@class='productshortDescriptions ']//div/text()")

        return short_description[0] if short_description else None

    def _long_description(self):
        long_description = self.tree_html.xpath("//div[@class='productshortDescriptions ']//div//ul")
        if long_description:
            long_description = html.tostring(long_description[0])

        return long_description

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_url_list = self.tree_html.xpath("//div[@class='zoom_img_col2']//img/@src")
        if not image_url_list:
            image_url_list = self.tree_html.xpath("//div[@class='zoom_img_col1']//img/@src")
        return image_url_list if image_url_list else None

    def _swatches(self):
        image_color_list = []
        swatches = []
        image_urls = self._image_urls()
        image_color_info = self.tree_html.xpath("//ul[@class='swatches Color']//li//span/text()")

        if image_color_info:
            for image_color in image_color_info:
                image_color_list.append(self._clean_text(image_color))
        if image_color_list:
            for image_color in image_color_list:
                for image_url in image_urls:
                    swatch = {
                        'color': image_color,
                        'hero_image': image_url
                    }
                    swatches.append(swatch)

        return  swatches

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//div[@class='product-sales-price ']/text()")

        return price[0] if price else None

    def _price_amount(self):
        price = self._price()
        if price:
            price = re.search('\d+\.\d*', price).group()

        return float(price) if price else 0

    def _price_currency(self):
        return 'USD'

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        out_of_stock = self.tree_html.xpath("//div[@class='add-to-cart-wrapper ']//span/text()")
        if out_of_stock:
            if out_of_stock[0].lower() == "out of stock":
                return 1
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//ol[@class='breadcrumb']//li//a/text()")

        return categories[1:] if categories else None

    def _brand(self):
        brand = self.tree_html.xpath("//meta[@property='og:brand']/@content")

        return brand[0] if brand else None

    def _sku(self):
        sku = self.tree_html.xpath("//span[@itemprop='productID']/text()")

        return sku[0].strip() if sku else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id": _product_id, \
 \
        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name, \
        "product_title": _product_title, \
        "model": _model, \
        "sku": _sku, \
        "description": _description, \
        "long_description": _long_description, \
        "swatches" : _swatches, \
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
        "in_stores_out_of_stock": _in_stores_out_of_stock, \
 \
        # CONTAINER : CLASSIFICATION
        "categories": _categories, \
        "brand": _brand, \
        }
