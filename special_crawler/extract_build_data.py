#!/usr/bin/python

import re
import json

from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words
from spiders_shared_code.build_variants import BuildVariants


class BuildScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is https://www.build.com/<product-name>"

    REVIEW_URL = "https://api.bazaarvoice.com/data/" \
                 "reviews.json?passkey=6s5v8vtfa857rmritww93llyn&apiversion=5.5" \
                 "&filter=productid%3Aeq%3Acp-{}&filter=contentlocale%3Aeq%3Aen_US" \
                 "&stats=reviews&filteredstats=reviews&include=products"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = None
        self._set_proxy()

    def check_url_format(self):
        m = re.match(r"^https?://www.build.com/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        self._extract_product_json()
        self.bv = BuildVariants()
        self.bv.setupCH(self.product_json)
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_product_json(self):
        try:
            self.product_json = re.search('({"environment":.*?});', html.tostring(self.tree_html), re.DOTALL)
            if self.product_json:
                self.product_json = json.loads(self.product_json.group(1))
        except:
            self.product_json = None

    def _product_id(self):
        return self.product_json['productCompositeId']

    def _site_id(self):
        return self._product_id()

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = re.search(r'description\":\"(.*?)\",.*(?=@type)', self.page_raw_text)
        if product_name:
            product_name = [product_name.group(1).decode('string-escape')]
        else:
            product_name = self.tree_html.xpath("//h2[contains(@class, 'js-sub-heading')]/text()")
        return product_name[0] if product_name else None

    def _product_title(self):
        return self._product_name()

    def _model(self):
        return self.product_json['selectedFinish']['uniqueId']

    def _upc(self):
        return self.product_json['selectedFinish']['upc']

    def _description(self):
        short_description = self.tree_html.xpath("//h2[@class='sub-text js-sub-heading']/text()")
        return short_description[0] if short_description else None

    def _long_description(self):
        long_description = []
        long_description_info = self.tree_html.xpath("//div[@class='description']//ul//li")
        for description in long_description_info:
            long_description.append(html.tostring(description))

        return ''.join(long_description)

    def _item_num(self):
        item_num = self.tree_html.xpath('//span[@class="code"]')
        return item_num[0].text_content() if item_num else None

    def _variants(self):
        return self.bv._variants()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []
        image_urls_info = self.tree_html.xpath("//div[contains(@class, 'js-gallery-thumbnail')]//img/@src")
        for image_url in image_urls_info:
            image_urls.append(image_url.replace('h_50', 'h_320').replace('w_50', 'w_320'))

        return image_urls

    def _pdf_urls(self):
        pdf_urls = []
        pdf_urls_info = self.tree_html.xpath("//ul[contains(@class, 'attachment-list')]//li//a/@href")
        for pdf_url in pdf_urls_info:
            pdf_urls.append('https:' + pdf_url)

        return pdf_urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//div[@class='text-price']//span/text()")
        if price:
            price = price[0]
            if '-' in price:
                price = price.split('-')[0]
        return price

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        out_of_stock = self.product_json['selectedFinish']['isOutOfStock']
        if out_of_stock is False:
            return 0
        return 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//div[@class='breadcrumbs']//a/text()")

        return categories[1:] if categories else None

    def _sku(self):
        return self.product_json['selectedFinish']['sku']

    def _brand(self):
        return guess_brand_from_first_words(self._product_name())

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,
        "site_id": _site_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "model": _model,
        "upc": _upc,
        "brand": _brand,
        "description": _description,
        "long_description": _long_description,
        "item_num": _item_num,
        "variants": _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "pdf_urls": _pdf_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories
    }
