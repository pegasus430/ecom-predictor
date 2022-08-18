#!/usr/bin/python

import urllib
import re
import sys
import json

from lxml import html, etree
import time
import requests
from extract_data import Scraper


class ClarksCoUkScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.clarks.co.uk/p/<product-id>"
    REVIEW_URL = "http://homedepot.ugc.bazaarvoice.com/1999aa/{0}/reviews.djs?format=embeddedhtml"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        # whether product has any webcollage media
        self.product_json = None
        # whether product has any webcollage media
        self.review_json = None
        self.review_list = None
        self.is_review_checked = False

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://www.clarks.co.uk/p/[0-9]+?$", self.product_page_url)
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
            itemtype = self.tree_html.xpath('//div[@id="product" and @itemtype="http://schema.org/Product"]')

            if not itemtype:
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

    def _event(self):
        return None

    def _product_id(self):
        product_id = self.tree_html.xpath('//input[@id="ProductId"]/@value')[0]
        return product_id

    def _site_id(self):
        product_id = self.tree_html.xpath('//input[@id="ProductId"]/@value')[0]
        return product_id

    def _status(self):
        return "success"

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        name = self.tree_html.xpath("//h1[@itemprop='name']/span[@class='name']/text()")[0].strip()
        colour = self.tree_html.xpath("//h1[@itemprop='name']/span[@class='colour']/text()")[0].strip()

        return name + " " + colour

    def _product_title(self):
        name = self.tree_html.xpath("//h1[@itemprop='name']/span[@class='name']/text()")[0].strip()
        colour = self.tree_html.xpath("//h1[@itemprop='name']/span[@class='colour']/text()")[0].strip()

        return name + " " + colour

    def _title_seo(self):
        name = self.tree_html.xpath("//h1[@itemprop='name']/span[@class='name']/text()")[0].strip()
        colour = self.tree_html.xpath("//h1[@itemprop='name']/span[@class='colour']/text()")[0].strip()

        return name + " " + colour

    def _model(self):
        return None

    def _upc(self):
        return None

    def _features(self):
        feature_rows = self.tree_html.xpath("//table[@class='shoe-features']//tr")
        feature_list = []

        for row in feature_rows:
            feature_list.append(row.xpath("./th/text()")[0] + ": " + row.xpath("./td/text()")[0])

        if feature_list:
            return feature_list

        return None

    def _feature_count(self):
        if self._features():
            return len(self._features())

        return None

    def _model_meta(self):
        return None

    def _description(self):
        description = self.tree_html.xpath("//div[@id='ProductDescription_0']")[0].text_content().strip()

        if description:
            return description

        return None

    def _long_description(self):
        return None



    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        return None

    def _image_urls(self):        
        image_list = self._find_between(html.tostring(self.tree_html), "function(){imageUrls=", ";zoomImageUrls=")
        image_list = json.loads(image_list)
        image_list = ["http:" + url for url in image_list]

        if image_list:
            return image_list

        return None

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    def _video_urls(self):
        return None

    def _video_count(self):
        videos = self._video_urls()

        if videos:
            return len(videos)

        return 0

    def _pdf_urls(self):
        return None

    def _pdf_count(self):
        if self._pdf_urls():
            return len(self._pdf_urls())

        return 0

    def _webcollage(self):
        return None

    def _htags(self):
        htags_dict = {}
        # add h1 tags text to the list corresponding to the "h1" key in the dict
        htags_dict["h1"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h1//text()[normalize-space()!='']"))
        # add h2 tags text to the list corresponding to the "h2" key in the dict
        htags_dict["h2"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h2//text()[normalize-space()!='']"))
        return htags_dict

    def _keywords(self):
        return self.tree_html.xpath("//meta[@name='keywords']/@content")[0]

    def _no_image(self):
        return None
    
    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        if self._review_count() >0:
            return float(self.tree_html.xpath("//meta[@itemprop='ratingValue']/@content")[0])

        return None

    def _review_count(self):
        if self.tree_html.xpath("//meta[@itemprop='reviewCount']/@content"):
            return int(self.tree_html.xpath("//meta[@itemprop='reviewCount']/@content")[0])

        return 0

    def _max_review(self):
        if self._review_count() == 0:
            return None

        self._reviews()

        for i, review in enumerate(self.review_list):
            if review[1] > 0:
                return 5 - i

    def _min_review(self):
        if self._review_count() == 0:
            return None

        self._reviews()

        for i, review in enumerate(reversed(self.review_list)):
            if review[1] > 0:
                return i + 1

    def _reviews(self):
        if self.is_review_checked:
            return self.review_list

        self.is_review_checked = True

        if self._review_count() == 0:
            self.review_list = None
            return None

        review_list = [[5, 0], [4, 0], [3, 0], [2, 0], [1, 0]]

        for ratingValue in self.tree_html.xpath("//span[@itemprop='reviewRating']/meta[@itemprop='ratingValue']/@content"):
            review_list[5 - int(ratingValue)][1] = review_list[5 - int(ratingValue)][1] + 1

        self.review_list = review_list

        return self.review_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        return self.tree_html.xpath("//dd[@class='price the-normal-price']/text()")[0].strip()

    def _price_amount(self):
        return float(self.tree_html.xpath("//span[@itemprop='offers']/meta[@itemprop='price']/@content")[0])

    def _price_currency(self):
        return self.tree_html.xpath("//meta[@itemprop='priceCurrency']/@content")[0]

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self.tree_html.xpath("//li[@class='instock-status']/text()"):
            if self.tree_html.xpath("//li[@class='instock-status']/text()")[0].strip() == "Out of stock":
                return 1

        return 0

    def _in_stores_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    def _seller_from_tree(self):
        return None

    def _marketplace_sellers(self):
        return None

    def _marketplace_lowest_price(self):
        return None





    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        return [self._find_between(html.tostring(self.tree_html), ',product_category:"', '",')]

    def _category_name(self):
        return self._categories()[-1]
    
    def _brand(self):
        return None



    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces
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
        "event" : _event, \
        "product_id" : _product_id, \
        "site_id" : _site_id, \
        "status" : _status, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "model" : _model, \
        "upc" : _upc,\
        "features" : _features, \
        "feature_count" : _feature_count, \
        "model_meta" : _model_meta, \
        "description" : _description, \
        "long_description" : _long_description, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count" : _image_count,\
        "image_urls" : _image_urls, \
        "video_count" : _video_count, \
        "video_urls" : _video_urls, \
        "no_image" : _no_image, \
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
        "in_stores" : _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "in_stores_out_of_stock": _in_stores_out_of_stock, \
        "marketplace" : _marketplace, \
        "marketplace_sellers" : _marketplace_sellers, \
        "marketplace_lowest_price" : _marketplace_lowest_price, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "category_name" : _category_name, \
        "brand" : _brand, \



        "loaded_in_seconds" : None, \
        }

    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = { \
        "mobile_image_same" : _mobile_image_same, \
    }
