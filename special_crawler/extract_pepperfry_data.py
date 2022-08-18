#!/usr/bin/python

import re
import lxml
import lxml.html
import requests
import json

from itertools import groupby

from lxml import html, etree
from extract_data import Scraper
from spiders_shared_code.pepperfry_variants import PepperfryVariants


class PepperfryScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.pepperfry.com/<product-name-id>.html"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        # whether product has any webcollage media
        self.product_json = None
        self.is_product_json_checked = False
        self.pv = PepperfryVariants()

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """

        m = re.match(r"^http://www\.pepperfry\.com/.*\.html$", self.product_page_url)

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
            if not self.tree_html.xpath("//div[@itemscope and @itemtype='http://schema.org/Product']"):
                raise Exception
        except Exception:
            return True

        self.pv.setupCH(self.tree_html)

        self._extract_product_json()

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
        return self.tree_html.xpath("//input[@id='product_id']/@value")[0]

    def _extract_product_json(self):
        if self.is_product_json_checked:
            return self.product_json

        self.is_product_json_checked = True

        try:
            script_texts = " " . join(self.tree_html.xpath("//script/text()"))
            start_index = script_texts.find("var product = ") + len("var product = ")

            if start_index < 0:
                return None

            end_index = script_texts.find("$(window).load(function()", start_index)
            script_texts = script_texts[start_index:end_index]
            script_texts = script_texts[:script_texts.rfind(";")]
            self.product_json = json.loads(script_texts)
        except:
            self.product_json = None

        return self.product_json

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath("//h2[@itemprop='name']/text()")[0].strip()

    def _product_title(self):
        return self.tree_html.xpath("//h2[@itemprop='name']/text()")[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath("//h2[@itemprop='name']/text()")[0].strip()

    def _model(self):
        return None

    def _features(self):
        try:
            return self.tree_html.xpath("//div[@id='other_details_panel_1']//ul/li/text()")
        except:
            return None

    def _feature_count(self):
        features = self._features()

        if not features:
            return 0

        return len(features)

    def _description(self):
        return self.tree_html.xpath("//div[@id='overview_tab']")[0].text_content().strip()

    # extract product long description from its product product page tree
    # ! may throw exception if not found
    # TODO:
    #      - keep line endings maybe? (it sometimes looks sort of like a table and removing them makes things confusing)
    def _long_description(self):
        return None

    def _ingredients(self):
        return None

    def _ingredients_count(self):
        return 0

    def _variants(self):
        return self.pv._variants()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        pass
        
    def _image_urls(self):
        image_urls = self.tree_html.xpath("//div[contains(@class, 'vip_thumbs_scroller')]//a[contains(@id, 'img_gallery')]/img/@src")

        if not image_urls:
            return None

        image_urls = [url.replace("90x99", "800x880") for url in image_urls]

        return image_urls

    def _image_count(self):
        image_urls = self._image_urls()

        if not image_urls:
            return 0

        return len(image_urls)

    def _video_urls(self):
        return None

    def _video_count(self):
        return 0

    # return dictionary with one element containing the PDF
    def _pdf_urls(self):
        return None

    def _pdf_count(self):
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
        return "Rs." + str(self.product_json["price"])

    def _price_amount(self):
        return float(self.product_json["price"])

    def _price_currency(self):
        return self.product_json["currency"]

    def _site_online(self):
        return 1

    def _in_stores(self):
        return 0

    def _site_online_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    def _marketplace_prices(self):
        return None

    def _marketplace_sellers(self):
        return None

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################    
    def _categories(self):
        return self.product_json["category"][1:]

    def _category_name(self):
        return self.product_json["category"][-1]

    def _brand(self):
        features = self._features()

        try:
            for feature in features:
                if feature.startswith("Brand:"):
                    return feature[len("Brand:"):].strip()
        except:
            pass

        return None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    def _clean_text(self, text):
        text = re.sub("&nbsp;", " ", text).strip()

        return text

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
        "variants": _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count" : _image_count,\
        "image_urls" : _image_urls, \
        "video_count" : _video_count, \
        "video_urls" : _video_urls, \
        "pdf_count" : _pdf_count, \
        "pdf_urls" : _pdf_urls, \
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
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "in_stores" : _in_stores, \
        "marketplace": _marketplace, \
        "marketplace_prices" : _marketplace_prices, \
        "marketplace_sellers": _marketplace_sellers, \

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
