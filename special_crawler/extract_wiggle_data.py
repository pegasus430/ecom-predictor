#!/usr/bin/python

import re
import lxml
import lxml.html
import requests
import json

from itertools import groupby

from lxml import html, etree
from extract_data import Scraper
from spiders_shared_code.jcpenney_variants import JcpenneyVariants


class WiggleScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www\.wiggle\.co\.uk/product-name/"

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """

        m = re.match(r"^http://www\.wiggle\.co\.uk/.*/$", self.product_page_url)

        return not not m

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """

        try:
            product_name = self.tree_html.xpath('//h1[@id="product-display-name"]')

            if not product_name:
                raise Exception()

        except Exception:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _canonical_link(self):
        canonical_link = self.tree_html.xpath("//link[@rel='canonical']/@href")[0]

        return canonical_link

    def _url(self):
        return self.product_page_url

    def _product_id(self):
        product_json = json.loads(re.search('window.universal_variable.product = (.+?)\n', html.tostring(self.tree_html)).group(1))

        return product_json["id"]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath('//h1[@id="product-display-name"]/text()')[0].strip()

    def _product_title(self):
        return self.tree_html.xpath('//h1[@id="product-display-name"]/text()')[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath('//h1[@id="product-display-name"]/text()')[0].strip()

    def _model(self):
        return None

    def _features(self):
        return None

    def _feature_count(self):
        return 0

    def _description(self):
        return self.tree_html.xpath("//span[@class='item-desc']/text()")[0].strip()

    # extract product long description from its product product page tree
    # ! may throw exception if not found
    # TODO:
    #      - keep line endings maybe? (it sometimes looks sort of like a table and removing them makes things confusing)
    def _long_description(self):
        description_block = self.tree_html.xpath("//div[@id='tabDescription']")[0]
        long_description = ""
        long_description_start = False

        for element in description_block:
            if element.tag == "a" and element.attrib["rel"] == "Buy Now":
                break

            long_description = long_description + html.tostring(element)

        if not long_description.strip():
            return None
        else:
            return long_description

    def _ingredients(self):
        return None

    def _ingredients_count(self):
        return 0


    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        pass

    def _image_urls(self):
        image_urls = self.tree_html.xpath("//ul[@id='gallery']//img/@src")

        if not image_urls:
            image_urls = self.tree_html.xpath("//div[@id='mainImageWrapper']//img/@src")

            image_urls = ["http:" + url for url in image_urls]

        if not image_urls:
            return None

        return image_urls

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    def _video_urls(self):
        return None

    def _video_count(self):
        return 0

    # return dictionary with one element containing the PDF
    def _pdf_urls(self):
        return None

    def _pdf_count(self):
        return 0

    def _webcollage(self):
        return 0

    def _htags(self):
        htags_dict = {}
        htags_dict["h1"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h1//text()[normalize-space()!='']"))
        htags_dict["h2"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h2//text()[normalize-space()!='']"))

        return htags_dict

    def _keywords(self):
        return self.tree_html.xpath('//meta[@name="keywords"]/@content')[0].strip()

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        product_json = json.loads(re.search('window.universal_variable.product = (.+?)\n', html.tostring(self.tree_html)).group(1))

        return float(product_json["review_rating"])

    def _review_count(self):
        product_json = json.loads(re.search('window.universal_variable.product = (.+?)\n', html.tostring(self.tree_html)).group(1))

        return int(product_json["review_volume"])

    def _max_review(self):
        return None

    def _min_review(self):
        return None

    def _reviews(self):
        return None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        return self.tree_html.xpath("//div[@class='unit-price']/text()")[0]

    def _price_amount(self):
        product_json = json.loads(re.search('window.universal_variable.product = (.+?)\n', html.tostring(self.tree_html)).group(1))

        return float(product_json["unit_sale_price"])

    def _price_currency(self):
        return "USD"

    def _owned(self):
        return 0

    def _marketplace(self):
        return 0

    def _site_online(self):
        return 1

    def _in_stores(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _marketplace_sellers(self):
        return None

    def _marketplace_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        product_json = json.loads(re.search('window.universal_variable.product = (.+?)\n', html.tostring(self.tree_html)).group(1))

        return product_json["categories"]

    def _category_name(self):
        product_json = json.loads(re.search('window.universal_variable.product = (.+?)\n', html.tostring(self.tree_html)).group(1))

        return product_json["categories"][-1]

    def _brand(self):
        return None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    def _clean_text(self, text):
        return re.sub("&nbsp;", " ", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "url" : _url, \
        "product_id" : _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "model" : _model, \
        "features" : _features, \
        "feature_count" : _feature_count, \
        "description" : _description, \
        "long_description" : _long_description, \
        "ingredients": _ingredients, \
        "ingredient_count": _ingredients_count,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count" : _image_count,\
        "image_urls" : _image_urls, \
        "video_count" : _video_count, \
        "video_urls" : _video_urls, \
        "pdf_count" : _pdf_count, \
        "pdf_urls" : _pdf_urls, \
        "webcollage" : _webcollage, \
        "htags" : _htags, \
        "keywords" : _keywords, \
        "canonical_link": _canonical_link,

        # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \
        "max_review" : _max_review, \
        "min_review" : _min_review, \
        "reviews" : _reviews, \
        # CONTAINER : SELLERS
        "price" : _price, \
        "price_amount" : _price_amount, \
        "price_currency" : _price_currency, \
        "owned" : _owned, \
        "marketplace" : _marketplace, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "in_stores" : _in_stores, \
        "marketplace_sellers" : _marketplace_sellers, \
        "marketplace_out_of_stock": _marketplace_out_of_stock, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "category_name" : _category_name, \
        "brand" : _brand, \
        }

    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = { \
        "mobile_image_same" : _mobile_image_same, \
    }
