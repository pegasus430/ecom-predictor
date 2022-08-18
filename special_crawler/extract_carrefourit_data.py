#!/usr/bin/python

import re
from lxml import html
from urlparse import urljoin
from extract_data import Scraper

class CarrefourItScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.carrefour.it/prodotti/<product_name> or " \
                          "http(s)://myshop.carrefour.it/(.*/)prodotto/<product_id>"

    def check_url_format(self):
        m1 = re.match(r'^https?://myshop\.carrefour\.it/.*/prodotto/\d+', self.product_page_url)
        m2 = re.match(r'^https?://www\.carrefour\.it/prodotti/[a-z0-9\-]*', self.product_page_url)
        return bool(m1 or m2)

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def not_a_product(self):
        if 'prodotti' in self.product_page_url or \
                self.tree_html.xpath('//section[@itemtype="http://schema.org/Product"]'):
            return False
        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath('//div[contains(@class, "product-detail")]//meta[@itemprop="productID"]/@content')
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        title = self.tree_html.xpath('//h1/text()')
        if not title:
            title = self.tree_html.xpath('//h1[contains(@class, "title")]/text()')
        return self._clean_text(title[0]) if title else None

    def _brand(self):
        brand = self.tree_html.xpath('//div[@class="top-info"]//span[@class="brand-name"]/text()')
        return brand[0] if brand else None

    def _product_title(self):
        return self._product_name()

    def _long_description(self):
        long_description = self.tree_html.xpath('//div[@id="info"]')
        return self._clean_text(html.tostring(long_description[0])) if long_description else None

    def _average_review(self):
        average_review = self.tree_html.xpath('//div[contains(@class, "rate")]/a[@class="star current"]')
        return len(average_review)

    def _review_count(self):
        review_count = self.tree_html.xpath('//span[@id="n-valut"]/text()')
        return int(review_count[0]) if review_count else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        img_urls = self.tree_html.xpath('//img[@class="owl-lazy"]/@data-src')
        if not img_urls:
            img_urls = self.tree_html.xpath('//div[@class="image"]/span/img/@src')
            img_urls = [urljoin(self.product_page_url, img_url) for img_url in img_urls]
        if not img_urls:
            img_urls = self.tree_html.xpath('//div[@class="main-pic"]/img[@id="thumb"]/@src')
        return img_urls

    def _pdf_urls(self):
        pdf_urls = self.tree_html.xpath('//a[contains(@href, ".pdf")]/@href')
        return pdf_urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.tree_html.xpath('//div[contains(@class, "product-detail")]//meta[@itemprop="price"]/@content')
        return float(price[0]) if price else None

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath('//div[@id="breadcrumb"]//a[@itemprop="item"]//span[@itemprop="name"]/text()')
        return categories if categories else None

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "long_description" : _long_description,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "pdf_urls": _pdf_urls,
        "average_review": _average_review,
        "review_count": _review_count,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
