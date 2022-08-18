#!/usr/bin/python

import re
import json
import traceback

from lxml import html
from extract_data import Scraper
from spiders_shared_code.bloomingdales_variants import BloomingDalesVariants

class BloomingdalesScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www(1).bloomingdales.com/shop/product/*"

    REVIEW_URL = "https://bloomingdales.ugc.bazaarvoice.com/7130aa/{}/reviews.djs?format=embeddedhtml"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.product_json = {}
        self.bv = BloomingDalesVariants()

        self._set_proxy()

    def check_url_format(self):
        m = re.match('https?://www1?.bloomingdales.com/shop/product/.*', self.product_page_url)
        return bool(m)

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def not_a_product(self):
        if not self._product_name():
            return True

    def _pre_scrape(self):
        product_json = re.search('var pdp = (.*?});', self.page_raw_text)
        self.product_json = json.loads(product_json.group(1))['product']
        self.bv.setupCH(self.product_json)

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath('//li[@id="productWebID"]')[0].text[8:]
        return product_id

    ##########################################
    ################ CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        name = self.tree_html.xpath('//div[@id="productName"]/text()')
        return name[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _description(self):
        description = self.tree_html.xpath('//div[contains(@class, "pdp_longDescription")]/text()')
        return description[0]

    def _variants(self):
        return self.bv._variants()

    ##########################################
    ################ CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self, tree = None):
        first_url = self.tree_html.xpath('//meta[@property="og:image"]/@content')
        primary_color = self.product_json.get('primaryColor')
        image_urls = self.product_json.get('colorwayAdditionalImages').get(primary_color).split(',')
        image_urls = ['https://images.bloomingdales.com/is/image/BLM/products/' + url for url in image_urls]
        image_urls.insert(0, first_url[0].split('?')[0])
        return image_urls

    ##########################################
    ################ CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = re.search('salePrice":\[(.*?)\]', html.tostring(self.tree_html), re.DOTALL)
        if not price:
            price = re.search('ORIGINAL_PRICE":"(.*?)"', html.tostring(self.tree_html), re.DOTALL)
        return '$' + price.group(1)

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        stock = re.search('"AVAILABILITY_MESSAGE":"(.*?)",', html.tostring(self.tree_html), re.DOTALL)
        if 'in stock' in stock.group(1).lower():
            return 0
        return 1

    def _marketplace(self):
        return 0

    ##########################################
    ################ CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath('//div[contains(@class, "breadCrumbs")]//a//text()')
        return [cat.strip() for cat in categories]

    def _brand(self):
        brand = self.tree_html.xpath('//a[@id="brandNameLink"]//text()')
        return brand[0]

    ##########################################
    ################ RETURN TYPES
    ##########################################
    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo" : _title_seo,
        "description" : _description,
        "variants" : _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,

        # CONTAINER : SELLERS
        "price" : _price,
        "in_stores" : _in_stores,
        "site_online" : _site_online,
        "site_online_out_of_stock" : _site_online_out_of_stock,
        "marketplace" : _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
