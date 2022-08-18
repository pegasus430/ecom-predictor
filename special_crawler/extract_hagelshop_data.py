#!/usr/bin/python

import urllib
import re
import sys
import json

from lxml import html, etree
import time
import requests
from extract_data import Scraper


class HagelShopScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.hagel-shop.de/<category-names>/<product-name>.html"

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
        m = re.match(r"^http://www.hagel-shop.de/.*?$", self.product_page_url)
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
            itemtype = self.tree_html.xpath('//div[contains(@class, "product-view")]/@itemtype')[0].strip()

            if itemtype != "http://schema.org/Product":
                raise Exception()

        except Exception:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_product_json(self):
        if self.product_json:
            return

        try:
            product_json_text = self._find_between(html.tostring(self.tree_html), "THD.PIP.products.primary = new THD.PIP.Product(", ");\r")
            self.product_json = json.loads(product_json_text)
        except:
            self.product_json = None

    def _canonical_link(self):
        canonical_link = self.tree_html.xpath("//link[@rel='canonical']/@href")[0]

        return canonical_link

    def _url(self):
        return self.product_page_url

    def _event(self):
        return None

    def _product_id(self):
        product_id = self.tree_html.xpath("//span[@itemprop='sku']/text()")[0].strip()
        return product_id

    def _site_id(self):
        product_id = self.tree_html.xpath("//span[@itemprop='sku']/text()")[0].strip()
        return product_id

    def _status(self):
        return "success"

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath("//h1[@itemprop='name']/text()")[0].strip()

    def _product_title(self):
        return self.tree_html.xpath("//h1[@itemprop='name']/text()")[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath("//h1[@itemprop='name']/text()")[0].strip()

    def _model(self):
        return None

    def _upc(self):
        return None

    def _features(self):
        features_label_list = self.tree_html.xpath("//table[@id='product-attribute-specs-table']/tbody/tr/th/text()")
        features_value_list = self.tree_html.xpath("//table[@id='product-attribute-specs-table']/tbody/tr/td/text()")
        features_list = []

        for index, feature_label in enumerate(features_label_list):
            features_list.append(feature_label.strip() + features_value_list[index].strip())

        if features_list:
            return features_list

        return None

    def _feature_count(self):
        if self._features():
            return len(self._features())

        return None

    def _model_meta(self):
        return None

    def _description(self):
        return self.tree_html.xpath("//div[@class='shortDescription']")[0].text_content().strip()

    def _long_description(self):
        return self.tree_html.xpath("//div[@id='product_tabs_description_tabbed_contents']/div[@class='std tabs-left']")[0].text_content().strip()


    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        return None

    def _image_urls(self):        
        image_urls = self.tree_html.xpath("//div[@class='more-views span5']/ul/li/a/img/@src")
        image_urls = [url.replace("/thumbnail/60x60/", "/image/") for url in image_urls]

        if image_urls:
            return image_urls

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
        if self._review_count() > 0:
            return float(self.tree_html.xpath("//span[@itemprop='ratingValue']")[0].text_content().strip())

    def _review_count(self):
        return int(self.tree_html.xpath("//span[@itemprop='ratingCount']")[0].text_content().strip())

    def _max_review(self):
        reviews = self._reviews()

        if reviews:
            for review in reversed(reviews):
                if review[1] > 0:
                    return review[0]

        return None

    def _min_review(self):
        reviews = self._reviews()

        if reviews:
            for review in reviews:
                if review[1] > 0:
                    return review[0]

        return None

    def _reviews(self):
        rating_star_list = self.tree_html.xpath("//div[@id='product_tabs_review_tabbed_contents']//div[@id='customer-reviews']//div[@class='rating']/@style")

        if rating_star_list:
            review_list = [[1, 0], [2, 0], [3, 0], [4, 0], [5, 0]]

            for rating_star in rating_star_list:
                rating = int(int(re.findall(r'\d+', rating_star)[0]) / 20)
                review_list[rating - 1][1] = review_list[rating - 1][1] + 1

            return review_list

        return None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        return self.tree_html.xpath("//span[@itemprop='price']")[0].text_content().strip()

    def _price_amount(self):
        return float(re.findall(r"\d*\.\d+|\d+", self._price().replace(",", "."))[0])

    def _price_currency(self):
        return self.tree_html.xpath("//meta[@itemprop='priceCurrency']/@content")[0]

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        try:
            if self.tree_html.xpath("//link[@itemprop='availability']/@href")[0].strip() != 'http://schema.org/InStock':
                return 1
        except:
            pass

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
        categories = self.tree_html.xpath("//ul[@itemprop='breadcrumb']//span[@itemprop='title']/text()")[1:]

        if categories:
            return categories

        return None

    def _category_name(self):
        if self._categories():
            return self._categories()[-1]

        return None
    
    def _brand(self):
        return self.tree_html.xpath("//span[@class='prod-brand']/img[@itemprop='logo']/@alt")[0].strip()

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
