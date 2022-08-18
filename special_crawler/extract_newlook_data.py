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



class NewlookScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.newlook.com/shop/.*$"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        # whether product has any webcollage media
        self.review_json = None
        self.review_list = None
        self.is_review_checked = False
        self.price_json = None

        self.is_analyze_media_contents = False
        self.video_urls = None
        self.video_count = 0
        self.pdf_urls = None
        self.pdf_count = 0
        self.wc_emc = 0
        self.wc_prodtour = 0
        self.wc_360 = 0
        self.wc_video = 0
        self.wc_pdf = 0

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://www.newlook.com/shop/.*$", self.product_page_url)

        return not not m

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """
        itemtype = self.tree_html.xpath('//div[@class="prod_info"]')
        if not itemtype:
            return True
        return False

    def _find_between(self, s, first, last):
        try:
            start = s.index(first) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _canonical_link(self):
        canonical_link = self.tree_html.xpath("//link[@rel='canonical']/@href")[0]

        return canonical_link

    def _url(self):
        return self.product_page_url

    def _product_id(self):
        return self.tree_html.xpath('//*[@itemprop="productID"]//text()')[0].strip()

    def _site_id(self):
        return self.tree_html.xpath('//*[@itemprop="productID"]//text()')[0].strip()

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath('//*[@itemprop="name"]//text()')[0].strip()

    def _product_title(self):
        return self.tree_html.xpath("//title//text()")[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath("//title//text()")[0].strip()

    def _model(self):
        return None

    def _features(self):
        return None

    def _feature_count(self):
        return 0

    def _description(self):
        description_block = self.tree_html.xpath("//span[@itemprop='description']")
        description = ""
        if len(description_block)>0:
            description = description_block[0].text_content().strip()

        return description

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
        return None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        pass

    def _image_urls(self):
        return ["http:"+b for b in self.tree_html.xpath("//div[@id='thumbs']//img/@src")]

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())
        return 0


    def _video_urls(self):
        return self.tree_html.xpath("//div[@id='thumbs']//li[contains(@class,'video')]/a/@href")

    def _video_count(self):
        return len(self._video_urls())

    # return dictionary with one element containing the PDF
    def _pdf_urls(self):
        return None

    def _pdf_count(self):
        return 0

    def _wc_emc(self):
        return None

    def _wc_prodtour(self):
        return None

    def _wc_360(self):
        v = self.tree_html.xpath("//a[contains(@class,'views_360')]")
        if len(v) >0 :
            return 1
        return 0

    def _wc_video(self):
        return 0

    def _wc_pdf(self):
        return None

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
        return self.tree_html.xpath('//*[@itemprop="price"]//text()')[0].strip()


    def _price_amount(self):
        price = self._price()
        price = price.replace(",", "")
        price_amount = re.findall(r"[\d\.]+", price)[0]
        return float(price_amount)

    def _price_currency(self):
        return "GBP"

    def _owned(self):
        return 1

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
        return self.tree_html.xpath("//div[@class='breadcrumb']/ul//li/a/text()")[1:]

    def _category_name(self):
        return self.tree_html.xpath("//div[@class='breadcrumb']/ul//li/a/text()")[-1]

    def _brand(self):
        return None

    def _click_and_collect(self):
        return 1
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
        "site_id" : _site_id, \
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
        "webcollage" : _webcollage, \
        "wc_360": _wc_360, \
        "wc_emc": _wc_emc, \
        "wc_pdf": _wc_pdf, \
        "wc_prodtour": _wc_prodtour, \
        "wc_video": _wc_video, \
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
        "click_and_collect": _click_and_collect, \

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

