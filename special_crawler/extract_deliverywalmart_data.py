#!/usr/bin/python

import re
import lxml
import lxml.html
import requests
import json
import ast

from itertools import groupby

from lxml import html, etree
from extract_data import Scraper


class DeliveryWalmartScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://delivery.walmart.com/usd-estore/m/product-detail.jsp?skuId=<skuid>"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.product_json = None
        self.product_json_url = "https://grocery-api.walmart.com/v0.1/api/product/{}"

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://delivery\.walmart\.com/usd-estore/m/product-detail\.jsp\?skuId=[0-9]+$", self.product_page_url)

        return not not m

    def extract_product_json(self):
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)
        contents = s.get(self.product_json_url.format(self._product_id()), headers=h, timeout=5).text
        self.product_json = json.loads(contents)

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """
        try:
            self.extract_product_json()
        except Exception:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _canonical_link(self):
        return self.product_page_url

    def _url(self):
        return self.product_page_url

    def _product_id(self):
        product_id = self.product_page_url[self.product_page_url.rfind("skuId=") + 6:]

        return product_id

    def _meta_tags(self):
        return None

    def _upc(self):
        return self.product_json["data"]["upc"][0]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.product_json["data"]["name"]

    def _product_title(self):
        return self.product_json["data"]["name"]

    def _title_seo(self):
        return self.product_json["data"]["name"]

    def _model(self):
        return self.product_json["data"]["modelNum"]

    def _features(self):
        features = self.product_json["data"]["specialFeatures"]

        if not features:
            return None

        features = features.split(",")

        return features

    def _feature_count(self):
        if self._features():
            return len(self._features())

        return 0

    def _description(self):
        return self.product_json["data"]["description"]

    # extract product long description from its product product page tree
    # ! may throw exception if not found
    # TODO:
    #      - keep line endings maybe? (it sometimes looks sort of like a table and removing them makes things confusing)
    def _long_description(self):
        return self.product_json["data"]["directions"]

    def _ingredients(self):
        contents = self.product_json["data"]["ingredients"]
        ingredients = []
        bracket_level = 0
        current = []
        # trick to remove special-case of trailing chars

        for c in (contents + ","):
            if c == "," and bracket_level == 0:
                ingredients.append("".join(current))
                current = []
            else:
                if c == "(":
                    bracket_level += 1
                elif c == ")":
                    bracket_level -= 1
                current.append(c)

        if not ingredients:
            return None

        ingredients = [ingredient.strip() for ingredient in ingredients]

        return ingredients

    def _ingredients_count(self):
        ingredients = self._ingredients()

        if not ingredients:
            return 0

        return len(ingredients)

    def _rollback(self):
        if not self.product_json["price"]["isRollback"]:
            return 0
        else:
            return 1

    def _no_image(self, url):
        """Overwrites the _no_image
        in the base class with an additional test.
        Then calls the base class no_image.

        Returns True if image in url is a "no image"
        image, False if not
        """

        # if image name is "no_image", return True
        if re.match(".*no.image\..*", url):
            return True
        else:
            return Scraper._no_image(self, url)

    def _nutrition_facts(self):
        return self.product_json["data"]["nutritionFacts"]

    def _nutrition_fact_count(self):
        # number of nutrition facts (of elements in the nutrition_facts list) - integer
        nutrition_facts = self._nutrition_facts()

        if nutrition_facts:
            return len(nutrition_facts)

        return 0

    def _nutrition_fact_text_health(self):
        nutrition_facts = self._nutrition_facts()
        serving_info_count = calories_info_count = 0
        nutrition_fact_count = self._nutrition_fact_count()

        if nutrition_fact_count == 0:
            return 0

        for nutrition_fact in nutrition_facts:
            if "serving" in nutrition_fact:
                serving_info_count = serving_info_count + 1

        for nutrition_fact in nutrition_facts:
            if "calories" in nutrition_fact:
                calories_info_count = calories_info_count + 1

        if serving_info_count == 0 or calories_info_count == 0 or nutrition_fact_count - serving_info_count - calories_info_count == 0:
            return 1

        return 2

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        pass
        
    def _image_urls(self):
        try:
            if self._no_image(self.product_json["data"]["images"]["thumbnail"]):
                return None
        except Exception, e:
            print "WARNING: ", e.message

        return self.product_json["data"]["images"]["large"]

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

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        return None

    def _review_count(self):
        return 0

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
        return "$" + str(self.product_json["price"]["list"])

    def _price_amount(self):
        return self.product_json["price"]["list"]

    def _price_currency(self):
        return "USD"

    def _marketplace(self):
        return 0

    def _site_online(self):
        return 1

    def _in_stores(self):
        return 1

    def _site_online_out_of_stock(self):
        if self.product_json["data"]["isOutOfStock"]:
            return 1

        return 0

    def _marketplace_sellers(self):
        return None

    def _marketplace_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        return None

    def _category_name(self):
        return None

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
        "meta_tags": _meta_tags,
        "upc": _upc,
        "rollback": _rollback,
        "nutrition_facts": _nutrition_facts, \
        "nutrition_fact_count": _nutrition_fact_count, \
        "nutrition_fact_text_health": _nutrition_fact_text_health, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count" : _image_count,\
        "image_urls" : _image_urls, \
        "video_count" : _video_count, \
        "video_urls" : _video_urls, \
        "pdf_count" : _pdf_count, \
        "pdf_urls" : _pdf_urls, \
        "webcollage" : _webcollage, \
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
