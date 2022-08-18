#!/usr/bin/python

import re
import urlparse

from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words


class ShoppersdrugmartScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www1.shoppersdrugmart.ca/en/<product-name>"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?passkey=caX7JsVasecVzM59tquUbkFfzRcA0T09c47X1SmsB70d8" \
                 "&apiversion=5.5&displaycode=11365-en_ca&resource.q0=products&filter.q0=id%3Aeq%3A{0}" \
                 "&stats.q0=reviews"

    def check_url_format(self):
        m = re.match(r"https?://www1.shoppersdrugmart.ca/en/.*?", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')
        if not itemtype or (itemtype and itemtype[0] != "product"):
            return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath("//div[@class='md-pdp-spec-value']/text()")
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[@itemprop='name']/text()")
        return product_name[0] if product_name else None

    def _description(self):
        desc = self.tree_html.xpath("//meta[@name='description']/@content")
        return desc[0] if desc else None

    def _price(self):
        return None # Necessary to avoid infinite recursion due to defitions in extract_data.py

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        images = []
        img_urls = self.tree_html.xpath("//span[@class='md-pdp-gallery-thumbnail-inner-container']//img/@src")
        for img in img_urls:
            images.append(urlparse.urljoin(self.product_page_url, img))
        return images if images else None

    def _sku(self):
        return self._product_id()

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
        categories = []
        cat_data = self.tree_html.xpath("//ul[@class='wg-hdr-nav-horizontal-sbu-list']//li")
        for cat in cat_data:
            if 'wg-hdr-nav-hor-sbu-active' in html.tostring(cat):
                categories.append(cat.xpath(".//a/text()")[0])
                break
            else:
                categories.append(cat.xpath(".//a/text()")[0])
        return categories

    def _brand(self):
        brand = guess_brand_from_first_words(self._product_name())
        return brand if brand else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\r\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "description": _description,
        "price": _price,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "sku": _sku,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand
        }
