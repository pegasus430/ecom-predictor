#!/usr/bin/python

import re
import json
import requests

from lxml import html
from extract_data import Scraper
from spiders_shared_code.oldnavy_variants import OldnavyVariants


class OldnavyScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://oldnavy(.gap).com/browse/product.do?<product-id> or " \
        "http://www.oldnavy.com/products/<product-name>-<product-id>.jsp"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
            "passkey=68zs04f4b1e7jqc41fgx0lkwj" \
            "&apiversion=5.5" \
            "&displaycode=3755_31_0-en_us" \
            "&resource.q0=products" \
            "&filter.q0=id:eq:{}" \
            "&stats.q0=reviews"

    def __init__(self, **kwargs):  # **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.product_json = None
        self.ov = OldnavyVariants()

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries(use_session = True)

    def check_url_format(self):
        m = re.match(r"^http://oldnavy(.gap)?.com/browse/product.do\?.*", self.product_page_url)
        n = re.match(r"^http://www.oldnavy.com/products/.*.jsp", self.product_page_url)
        return bool(m or n)

    def not_a_product(self):
        self._extract_product_json()
        self.ov.setupCH(self.tree_html, self.product_json)

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_product_json(self):
        product_json = self._find_between(html.tostring(self.tree_html), 'gap.pageProductData = ', '};')
        try:
            if product_json:
                self.product_json = json.loads(product_json + '}')
        except:
            self.product_json = None

    def _product_id(self):
        product_id = re.search('pid=(\d+)', self.product_page_url)
        if product_id:
            return product_id.group(1)

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.product_json['name']

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _model(self):
        return self._product_id()

    def _description(self):
        short_description = self.tree_html.xpath("//ul[@class='sp_top_sm dash-list']")
        if short_description:
            short_description = html.tostring(short_description[0])
            short_description = re.sub(' +', ' ', self._clean_text(short_description))
        return short_description

    def _long_description(self):
        long_description = self.tree_html.xpath("//ul[@class='sp_top_sm dash-list']")

        if long_description:
            long_description = html.tostring(long_description[-1])
            long_description = re.sub(' +', ' ', self._clean_text(long_description))

        return long_description

    def _no_longer_available(self):
        if self._product_name():
            return 0
        return 1

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _video_urls(self):
        video_url_list = []
        site_domain = 'http://oldnavy.gap.com'

        product_image_info = self.product_json['productImages']
        product_color_images = self.product_json['variants'][0]['productStyleColors'][0][0]['productStyleColorImages']

        for product_color in product_color_images:
            if product_image_info[product_color]['video']:
                video_url_list.append(site_domain + product_image_info[product_color]['video'])

        return video_url_list

    def _image_urls(self):
        image_url_list = []
        site_domain = 'http://oldnavy.gap.com'
        color_stock_status = []
        current_color_image = self.product_json['currentColorMainImage']

        in_stock_color = {}

        for variant in self.product_json['variants']:
            if not variant['inStock']:
                continue
            for product_style_colors in variant['productStyleColors']:
                for color in product_style_colors:
                    if color['inStock']:
                        in_stock_color[color['largeImagePath']] = color['productStyleColorImages']
                        color_stock_status.append(color['productStyleColorImages'][0].split('_')[0])

        if current_color_image not in in_stock_color:
            current_color_image = in_stock_color.keys()[0]
        for color_image in in_stock_color[current_color_image]:
            if color_image.split('_')[0] in color_stock_status:
                image_url_list.append(site_domain + self.product_json['productImages'][color_image]['large'])

        return image_url_list

    def _variants(self):
        return self.ov._variants()

    def _swatches(self):
        return self.ov.swatches()

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        self.max_price = self.product_json['currentMaxPrice']
        self.min_price = self.product_json['currentMinPrice']
        if self.min_price == self.max_price:
            return self.min_price
        return (self.min_price + "-" + self.max_price)

    def _price_amount(self):
        price = self.product_json['currentMinPrice']
        if price:
            return float(re.search('\d+\.?\d*', price).group())

    def _price_currency(self):
        return 'USD'

    def _in_stores(self):
        if not self._no_longer_available():
            return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self._no_longer_available():
            return 1
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        return 'OLD NAVY'

    def _size_chart(self):
        size_chart_url_link = self.tree_html.xpath("//div[@class='fit-information']//a/@data-url")
        if size_chart_url_link:
            return 1
        return 0

    def _sku(self):
        return self.product_json['categoryId']

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
        "title_seo": _title_seo, \
        "model": _model, \
        "sku": _sku, \
        "description": _description, \
        "long_description": _long_description, \
        "swatches": _swatches, \
        "variants": _variants, \
 \
        # CONTAINER : PAGE_ATTRIBUTES
        "size_chart": _size_chart, \
        "video_urls": _video_urls, \
        "image_urls": _image_urls, \
        "no_longer_available": _no_longer_available, \
 \
        # CONTAINER : SELLERS
        "price": _price, \
        "price_amount": _price_amount, \
        "price_currency": _price_currency, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
 \
        # CONTAINER : CLASSIFICATION
        "brand": _brand, \
        }
