#!/usr/bin/python

import re
import json
import traceback
import requests

from extract_data import Scraper


class BootsScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.boots.com/en/<product-name>_<product-id>"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
            "passkey=324y3dv5t1xqv8kal1wzrvxig" \
            "&apiversion=5.5" \
            "&displaycode=2111-en_gb" \
            "&resource.q0=products" \
            "&filter.q0=id:eq:{}" \
            "&stats.q0=reviews"

    IMAGE_URL = "https://boots.scene7.com/is/image/{}?wid=500&hei=500&fmt=jpg"

    S7VIEWER_URL = "https://boots.scene7.com/is/image/{}?req=set,json,UTF-8" \
                   "&labelkey=label&handler=s7classics7sdkJSONResponse"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.image_urls = []
        self.image_checked = False

        self._set_proxy()

    def check_url_format(self):
        m = re.match(r"^http://www.boots.com/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@name="pageName"]/@content')
        if itemtype and itemtype[0].strip() != 'ProductPage':
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath("//input[@id='product_ID']/@value")

        return product_id[0].strip() if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath(
            "//div[@id='estore_product_title']"
            "//h1[@itemprop='name']/text()"
        )

        return product_name[0].strip() if product_name else None

    def _product_title(self):
        product_title = self.tree_html.xpath("//title/text()")
        if product_title:
            product_title = product_title[0].replace("- Boots", "").strip()

        return product_title

    def _title_seo(self):
        return self._product_title()

    def _long_description(self):
        long_description = self.tree_html.xpath("//div[@id='estore_product_longdesc']/descendant::text()")
        long_description = self._clean_text(' '.join(long_description))

        return long_description

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        if self.image_checked:
            return self.image_urls

        self.image_checked = True

        try:
            s7_id = self.tree_html.xpath("//input[@id='s7viewerAsset']/@value")[0].strip()
        except Exception as e:
            print traceback.format_exc(e)
            return None

        response = requests.get(self.S7VIEWER_URL.format(s7_id), timeout=10)

        try:
            image_info = json.loads(self._find_between(response.text, 's7classics7sdkJSONResponse(', ',"");'))
            images = image_info['set']['item']
            if type(images) == dict:
                self.image_urls.append(self.IMAGE_URL.format(images['i']['n']))
            elif type(images) == list:
                for image in images:
                    self.image_urls.append(self.IMAGE_URL.format(image['i']['n']))
        except Exception as e:
            print traceback.format_exc(e)
            return None

        return self.image_urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath("//div[@id='PDP_productPrice']/text()")

        return price[0].strip() if price else None

    def _price_amount(self):
        price = self._price()
        try:
            price = float(re.search('\d+\.\d*', price).group())
        except Exception as e:
            print traceback.format_exc(e)
            price = 0.0

        return price

    def _price_currency(self):
        return 'GBP'

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        out_of_stock = 0
        try:
            stock_info = self.tree_html.xpath("//input[@id='isInStock']/@value")[0].strip()
            if stock_info == 'false':
                out_of_stock = 1
        except Exception as e:
            print traceback.format_exc(e)
            out_of_stock = 1

        return out_of_stock

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//div[@id='widget_breadcrumb']//a/text()")
        categories = filter(None, map(self._clean_text, categories))

        return categories[1:] if categories else None

    def _brand(self):
        brand = self.tree_html.xpath(
            "//div[@id='estore_productpage_template_container']/@class"
        )
        if brand:
            brand = brand[0].replace('brand_', '').strip()

        return brand

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id" : _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "long_description" : _long_description, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "price_amount" : _price_amount, \
        "price_currency" : _price_currency, \
        "site_online": _site_online, \
        "in_stores" : _in_stores, \
        "site_online_out_of_stock": _site_online_out_of_stock, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "brand" : _brand, \
        }
