#!/usr/bin/python
#  -*- coding: utf-8 -*-

import urllib
import re
import sys
import json
import os.path
import urllib, cStringIO
from io import BytesIO
from PIL import Image
import mmh3 as MurmurHash
from lxml import html
from lxml import etree
import time
import requests
from extract_data import Scraper


class BabysecurityScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www\.babysecurity\.co\.uk/([a-zA-Z0-9\-\_/]+)"

    reviews_tree = None
    max_score = None
    min_score = None
    review_count = None
    average_review = None
    reviews = None

    def check_url_format(self):
        # for ex: http://www.babysecurity.co.uk/bornfree-deco-bottles-5oz-3-pack-0-3-months.html#.VJjkDDMDQE
        m = re.match(r"^http://www\.babysecurity\.co\.uk/([a-zA-Z0-9\-\_/]+)", self.product_page_url)
        return not not m

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """
        image_url = self.tree_html.xpath("//div[contains(@class,'product-img-column')]//p[contains(@class,'product-image')]")
        if len(image_url) < 1:
            return True
        return False
    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _url(self):
        return self.product_page_url

    def _product_id(self):
        return None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath("//div[@class='product-name']/h1/text()")[0].strip()

    def _product_title(self):
        return self.tree_html.xpath("//div[@class='product-name']/h1/text()")[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath("//title//text()")[0].strip()
    
    def _model(self):
        return None

    def _upc(self):
        return self.tree_html.xpath("//div[@class='sku']/text()")[0].strip()

    def _features(self):
        return None

    def _feature_count(self):
        if self._features() is None:
            return 0
        return len(self._features())

    def _model_meta(self):
        return None

    def _description(self):
        description = self._description_helper()
        if len(description) < 1:
            return self._long_description_helper()
        return description

    def _description_helper(self):
        rows = self.tree_html.xpath("//div[starts-with(@class, 'product-shop')]/text()")
        line_txts = []
        for row in rows:
            if len(row.strip()) > 0:
                line_txts += [self._clean_text(r) for r in row.split(u'\u2022') if len(self._clean_text(r)) > 0]
        return "\n".join(line_txts)


    def _long_description(self):
        description = self._description_helper()
        if len(description) < 1:
            return None
        return self._long_description_helper()

    def _long_description_helper(self):
        panels = self.tree_html.xpath("//div[@class='panel']")
        for panel in panels:
            try:
                if panel.xpath("./h2/text()")[0].strip() == "Details":
                    #this is description tab
                    rows = panel.xpath("./div[@class='std']//text()")
            except IndexError:
                pass
        rows = [self._clean_text(r) for r in rows if len(self._clean_text(r)) > 0]
        description = "\n".join(rows)
        return description

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    #returns 1 if the mobile version is the same, 0 otherwise
    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        image_url = self.tree_html.xpath("//div[starts-with(@class,'thumbnails')]//div[@class='item']//a/@href")
        if len(image_url) < 1:
            image_url = self.tree_html.xpath("//div[contains(@class,'product-img-column')]//p[contains(@class,'product-image')]//a[contains(@class,'cloud-zoom')]/@href")
            image_url = [r for r in image_url if "no-image." not in r]
        if len(image_url) < 1:
            return None
        return image_url

    def _image_count(self):
        image_urls = self._image_urls()
        if image_urls:
            return len(image_urls)
        return 0

    def _video_urls(self):
        video_url = self.tree_html.xpath("//div[starts-with(@class,'product-img-column')]//iframe/@src")
        if len(video_url) < 1:
            video_url = self.tree_html.xpath("//iframe/@src")
            if len(video_url) < 1:
                return None
        return video_url

    def _video_count(self):
        urls = self._video_urls()
        if urls:
            return len(urls)
        return 0

    def _pdf_urls(self):
        pdfs = self.tree_html.xpath("//a[contains(@href,'.pdf')]")
        pdf_hrefs = []
        for pdf in pdfs:
            pdf_url_txts = [self._clean_text(r) for r in pdf.xpath(".//text()") if len(self._clean_text(r)) > 0]
            if len(pdf_url_txts) > 0:
                pdf_hrefs.append(pdf.attrib['href'])
        if len(pdf_hrefs) < 1:
            return None
        return pdf_hrefs

    def _pdf_count(self):
        urls = self._pdf_urls()
        if urls is not None:
            return len(urls)
        return 0

    def _webcollage(self):
        atags = self.tree_html.xpath("//a[contains(@href, 'webcollage.net/')]")
        if len(atags) > 0:
            return 1
        return 0

    # extract htags (h1, h2) from its product product page tree
    def _htags(self):
        htags_dict = {}
        # add h1 tags text to the list corresponding to the "h1" key in the dict
        htags_dict["h1"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h1//text()[normalize-space()!='']"))
        # add h2 tags text to the list corresponding to the "h2" key in the dict
        htags_dict["h2"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h2//text()[normalize-space()!='']"))
        return htags_dict

    def _keywords(self):
        return self.tree_html.xpath("//meta[@name='keywords']/@content")[0]

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################
    #populate the reviews_tree variable for use by other functions
    def _load_reviews(self):
        if not self.max_score or not self.min_score:
            reviews = self.tree_html.xpath("//div[contains(@class,'box-reviews')]//dd//div[@class='rating-box']//div[@class='rating']/@style")
            rv_scores = []
            for review in reviews:
                review_score = re.findall(r'width\:([0-9]+)%', review)[0]
                review_score = int(5.0*float(review_score)/100)
                rv_scores.append(review_score)
            self.max_score = max(rv_scores)
            self.min_score = min(rv_scores)
            self.reviews = []
            for i in range(1,6):
                if rv_scores.count(i) > 0:
                    self.reviews.append([i, rv_scores.count(i)])


    def _average_review(self):
        avg_review = self.tree_html.xpath("//div[starts-with(@class,'product-shop')]//div[@class='ratings']//div[@class='rating-box']//div[@class='rating']/@style")[0]
        avg_review = re.findall(r'width\:([0-9]+)%', avg_review)[0]
        avg_review = round(5.0*float(avg_review)/100, 2)
        return avg_review

    def _review_count(self):
        review_cnt = self.tree_html.xpath("//div[@class='ratings']//a[@id='goto-reviews']/text()")[0].strip()
        review_cnt = re.findall(r'^([0-9]+)', review_cnt)[0]
        return int(review_cnt)

    def _max_review(self):
        self._load_reviews()
        return self.max_score

    def _min_review(self):
        self._load_reviews()
        return self.min_score

    def _reviews(self):
        self._load_reviews()
        return self.reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        try:
            price = self.tree_html.xpath("//div[contains(@class,'product-type-data')]//p[@class='special-price']//span[@class='price']//text()")[0].strip()
        except IndexError:
            price = self.tree_html.xpath("//div[contains(@class,'product-type-data')]//span[@class='regular-price']//span[@class='price']//text()")[0].strip()
        return price

    def _in_stores_only(self):
        return None

    def _in_stores(self):
        return None

    def _owned(self):
        return 1
    
    def _marketplace(self):
        return 0

    def _owned_out_of_stock(self):
        try:
            if 'Out of stock' in self.tree_html.xpath("//p[starts-with(@class,'availability')]//span/text()")[0].strip():
                return 1
        except IndexError:
            pass
        return 0

    def _marketplace_sellers(self):
        return None

    def _marketplace_lowest_price(self):
        return None

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        all = self.tree_html.xpath("//div[contains(@class, 'breadcrumbs')]//li//a//text()")
        out = [self._clean_text(r) for r in all]
        out = out[1:]
        if len(out) < 1:
            return None
        return out

    def _category_name(self):
        return self._categories()[-1]

    def _brand(self):
        brand = None
        trs = self.tree_html.xpath("//table[@class='data-table']//tr")
        for tr in trs:
            try:
                head_txt = tr.xpath("//th//text()")[0].strip()
                if head_txt == "Brand":
                    brand = tr.xpath("//td//text()")[0].strip()
            except IndexError:
                pass
        return brand

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
        "product_id" : _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "features" : _features, \
        "feature_count" : _feature_count, \
        "description" : _description, \
        "model" : _model, \
        "long_description" : _long_description, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls, \
        "image_count" : _image_count, \
        "pdf_urls" : _pdf_urls, \
        "pdf_count" : _pdf_count, \
        "video_urls" : _video_urls, \
        "video_count" : _video_count, \
        "webcollage" : _webcollage, \
        "htags" : _htags, \
        "keywords" : _keywords, \
        "mobile_image_same" : _mobile_image_same, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "in_stores_only" : _in_stores_only, \
        "in_stores" : _in_stores, \
        "owned" : _owned, \
        "owned_out_of_stock" : _owned_out_of_stock, \
        "marketplace": _marketplace, \
        "marketplace_sellers" : _marketplace_sellers, \
        "marketplace_lowest_price" : _marketplace_lowest_price, \

         # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \
        "max_review" : _max_review, \
        "min_review" : _min_review, \
        "reviews" : _reviews, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "category_name" : _category_name, \
        "brand" : _brand, \

        "loaded_in_seconds": None \
        }


    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = { \
    }

