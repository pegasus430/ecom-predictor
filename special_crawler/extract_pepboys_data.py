#!/usr/bin/python

import urllib
import re
import sys
import json
import ast
import HTMLParser

from lxml import html, etree
import time
import requests
from extract_data import Scraper


class PepboysScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is https://www.pepboys.com/.*"
    BASE_URL_REVIEWSREQ = 'https://pepboys.ugc.bazaarvoice.com/8514-en_us/{product_id}/reviews.djs?format=embeddedhtml'
    BASE_URL_WEBCOLLAGE = 'http://content.webcollage.net/cvs/smart-button?ird=true&channel-product-id={0}'

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        # whether product has any webcollage media
        self.product_json = None
        self.breadcrumb_list = None
        self.product = None
        self.full_description = None
        self.review_list = None
        self.review_count = None
        self.average_review = None
        self.max_review = None
        self.min_review = None
        self.images = None
        self.is_review_checked = False
        self.is_webcollage_checked = False
        self.webcollage_content = None
        self.wc_360 = 0
        self.wc_emc = 0
        self.wc_video = 0
        self.wc_pdf = 0
        self.wc_prodtour = 0

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^https://www.pepboys.com/.+$", self.product_page_url)
        return not not m

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """
        rows = self.tree_html.xpath("//div[contains(@class,'tdTireDetailPicHolder')]")
        if len(rows) > 0:
            return False
        return True

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
        arr = self.tree_html.xpath("//div[contains(@class,'j-results-item-container')]/@data-sku")
        if len(arr) > 0:
            return arr[0]
        return None

    def _site_id(self):
        return self._product_id()

    def _status(self):
        return "success"

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        arr = self.tree_html.xpath(
            "//div[contains(@class,'tdProductDetailItem')]"
            "//div[contains(@class,'row-fluid')]"
            "//h4[contains(@class,'margin-top-none')]/a/text()"
        )
        if len(arr) > 0:
            return self._clean_text(arr[0])
        return None

    def _product_title(self):
        return self.tree_html.xpath('//title')[0].text_content()

    def _title_seo(self):
        return self._product_title()

    def _model(self):
        return None

    def _upc(self):
        return None

    def _features(self):
        arr = self.tree_html.xpath("//div[contains(@class,'tdContentDesc')]//li/text()")

        return arr

    def _feature_count(self):
        if self._features():
            return len(self._features())

    def _model_meta(self):
        return None

    def _description(self):
        arr = self.tree_html.xpath("//div[contains(@class,'tdContentDesc')]/text()")
        arr = [r.strip() for r in arr if len(r.strip())>0]
        desc = "".join(arr)
        return self._clean_text(desc)

    def _long_description(self):
        description = ''

        if description:
            if description != self._description():
                return description

    def _ingredients(self):
        return None

    def _ingredient_count(self):
        return None

    def _variants(self):
        variants = []

        if variants:
            return variants

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        if self.images:
            return self.images

        image_urls = self.tree_html.xpath(
            "//div[contains(@class,'tdImgDetailLinks')]//img[@alt!='Play']/@src")
        self.images = image_urls

        if image_urls:
            return image_urls

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    def _video_urls(self):
        self._webcollage()

        video_urls = []

        for wcobj in re.findall(r'wcobj=\\"([^"]+)\\"', self.webcollage_content):
            if re.search('.flv$', wcobj.replace('\\', '')):
                video_urls.append( wcobj.replace('\\', ''))

        if video_urls:
            return video_urls

    def _video_count(self):
        videos = self.tree_html.xpath(
            "//div[contains(@class,'tdImgDetailLinks')]//img[@alt='Play']/@src")

        if videos:
            return len(videos)

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

    def _wc_360(self):
        self._webcollage()

        return self.wc_360

    def _wc_emc(self):
        self._webcollage()

        return self.wc_emc

    def _wc_pdf(self):
        self._webcollage()

        return self.wc_pdf

    def _wc_prodtour(self):
        self._webcollage()

        return self.wc_prodtour

    def _wc_video(self):
        self._webcollage()

        return self.wc_video

    def _htags(self):
        return None

    def _keywords(self):
        return self.tree_html.xpath("//meta[@name='keywords']/@content")[0]

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    # reviews
    def _review_count(self):
        cnt = self.tree_html.xpath('//span[@class="bvseo-reviewCount"]/text()')
        if cnt:
            return cnt[0]

    def _average_review(self):
        avg = self.tree_html.xpath('//span[@class="bvseo-ratingValue"]/text()')
        if avg:
            return avg[0]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        return '$' + str(self._price_amount())

    def _price_amount(self):
        arr = self.tree_html.xpath("//div[contains(@class,'price-stack')]//span[contains(@class,'ftPrice')]//text()")
        if len(arr) > 0:
            value = re.findall(r'[\d\.]+', arr[0])[0]
            return float(value)
        return None

    def _price_currency(self):
        return "USD"

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        detail_block = self.tree_html.xpath("//div[contains(@class, 'tdProductDetailItem')]")
        if "available today" in html.tostring(detail_block[0]).lower():
            return 0

        return 1

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
        arr = self.tree_html.xpath("//ul[contains(@class,'breadcrumb')]/li//text()")
        arr = [self._clean_text(r) for r in arr if len(self._clean_text(r))>0 and self._clean_text(r)!='/']
        return arr[1:]

    def _category_name(self):
        return self._categories()[-1]

    def _brand(self):
        return None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces
    def _clean_text(self, text):
        text = HTMLParser.HTMLParser().unescape( text)
        text = re.sub('[\r\n\t]', '', text)
        text = re.sub('>\s+<', '><', text)
        return re.sub('\s+', ' ', text).strip()

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
        "ingredients" : _ingredients, \
        "ingredient_count" : _ingredient_count, \
        "variants": _variants, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count" : _image_count,\
        "image_urls" : _image_urls, \
        "video_count" : _video_count, \
        "video_urls" : _video_urls, \
        "pdf_count" : _pdf_count, \
        "pdf_urls" : _pdf_urls, \
        "wc_360": _wc_360, \
        "wc_emc": _wc_emc, \
        "wc_video": _wc_video, \
        "wc_pdf": _wc_pdf, \
        "wc_prodtour": _wc_prodtour, \
        "webcollage" : _webcollage, \
        "htags" : _htags, \
        "keywords" : _keywords, \
        "canonical_link": _canonical_link, \

        # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \

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
