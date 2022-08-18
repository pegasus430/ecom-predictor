#!/usr/bin/python

import re
import traceback
from extract_data import Scraper
from lxml import html

class AbtScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.abt.com/.*"

    REVIEW_URL = "https://readservices-b2c.powerreviews.com/m/10201/l/en_US/product/{}/" \
                 "reviews?sort=Newest&filters=rating:5"

    def __init__(self, **kwargs):  # **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

    def check_url_format(self):
        m = re.match(r"^https?://www.abt.com/.*?", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[@id="productimagecontainer"]')) < 1:
            return True

        return False

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _extract_auth_key(self):
        auth_pwr = re.findall(r"api_key:\s'(.*?)'", html.tostring(self.tree_html))
        if auth_pwr:
            return auth_pwr[0]

    def _product_id(self):
        product_id = self.tree_html.xpath('//*[@name="product_id"]/@value')
        if product_id:
            return product_id[0]

    def _brand(self):
        brand = self.tree_html.xpath('//meta[@itemprop="brand"]/@content')
        return brand[0]

    def _product_name(self):
        return self._product_title()

    def _product_title(self):
        data = self.tree_html.xpath(
            '//h1[@id="product_title"]//text()'
        )

        title = ''
        for item in data:
            title += item
        return title

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        description = self.tree_html.xpath('//div[@id="cnet-content-solutions"]/following-sibling::p/text()')
        desc = ''.join([i + '\n' for i in description if i.strip()])
        return desc

    def _model(self):
        model = self.tree_html.xpath('//meta[@itemprop="model"]/@content')
        return model[0]

    def _upc(self):
        upc = self.tree_html.xpath('//meta[@itemprop="productID"]/@content')
        upc = re.search('upc:(.*)', upc[0], re.DOTALL).group(1)
        return upc

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//div[@id="prod_thumbs"]//img/@src')

        if image_urls:
            return ['http:' + x if x[:2] == '//' else x for x in image_urls]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath(
            '//span[@id="price"]'
            '/@content'
        )
        if not price:
            price = self.tree_html.xpath(
                '//span[@id="price"]'
                '/text()'
            )
        return '$' + price[0] if '$' not in price[0] else price[0]

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
        categories = self.tree_html.xpath('//div[@class="bread_crumbs"]'
                                          '//a/span/text()')
        return [self._clean_text(category) for category in categories[1:]]

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "brand": _brand,
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo": _title_seo,
        "description": _description,
        "model": _model,
        "upc": _upc,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,

        }
