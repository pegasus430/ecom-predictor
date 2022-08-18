#!/usr/bin/python

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
import time
import requests
from lxml.etree import tostring
from itertools import chain
from extract_data import Scraper

class BhinnekaScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.bhinneka.com/products/<product-sku>/<product-name>.aspx"

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://www.bhinneka.com/products/sku\d+/.+\.aspx$", self.product_page_url)

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
            itemtype = self.tree_html.xpath('//div[@id="ctl00_content_divfound"]/@itemtype')[0].strip()

            if itemtype != "http://schema.org/Product":
                raise Exception()

        except Exception:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _url(self):
        return self.product_page_url

    def _product_id(self):
        product_id = self.tree_html.xpath("//meta[@itemprop='productID']/@content")[0]

        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath('//h1[@itemprop="name"]/text()')[0].strip()

    def _product_title(self):
        return self.tree_html.xpath('//h1[@itemprop="name"]/text()')[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath('//head/title/text()')[0].strip()

    def _model(self):
        return self.tree_html.xpath('//meta[@itemprop="model"]/@content')[0]

    def _features(self):
        feature_html_list = self.tree_html.xpath('//table[@class="spesifications"]//tr')

        if not feature_html_list:
            return None

        features = []

        for feature in feature_html_list:
            feature_row = ''
            feature_row += " ".join([x for x in feature.itertext()])
            features.append(feature_row.strip())

        return features

    def _feature_count(self):
        feature_html_list = self.tree_html.xpath('//table[@class="spesifications"]//tr')

        if not feature_html_list:
            return 0

        return len(feature_html_list)

    def _description(self):
        items = self.tree_html.xpath('//div[@class="brdrTopSolid prodInfoSection"]//text()')

        if not items:
            return None

        short_description = ''

        for item in items:
            if item.replace('\r','').replace('\n','').strip() == '':
                continue
            short_description += '\n' + item

        return short_description.strip()

    # extract product long description from its product product page tree
    # ! may throw exception if not found
    # TODO:
    #      - keep line endings maybe? (it sometimes looks sort of like a table and removing them makes things confusing)
    def _long_description(self):
        overview = self.tree_html.xpath('//li[contains(@id, "tabTitleItem")]/text()')[0]

        if overview.strip() != "Overview":
            return None

        overview_tab_html = self.tree_html.xpath('//div[contains(@class, "tabContentSelected")]/div')
        overview_tab_text = ""

        for item in overview_tab_html:
            overview_tab_text += (" " . join([x for x in item.itertext()]).strip())

        return overview_tab_text.replace("\n","").replace("\r","")

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        pass
        
    def _image_urls(self):
        image_urls = self.tree_html.xpath('//div[@id="thumb"]/img/@src')

        if not image_urls:
            image_urls = self.tree_html.xpath('//div[@id="prodMedia"]/div/img/@src')

        if len(image_urls) == 1 and "no_picture" in image_urls[0]:
            return None

        return image_urls

    def _image_count(self):
        if self._image_urls() == None:
            return 0

        return len(self._image_urls())
    
    def _video_urls(self):
        video_urls = self.tree_html.xpath("//iframe[@allowfullscreen]/@src")

        if not video_urls:
            return None

        return video_urls

    def _video_count(self):
        return len(self._video_urls())

    # return dictionary with one element containing the PDF
    def _pdf_urls(self):
        pdf_urls = self.tree_html.xpath('//a[contains(@href, ".pdf")]/@href')
        pdf_urls[:] = ["http://www.bhinneka.com" + x for x in pdf_urls]

        if not pdf_urls:
            return None

        return pdf_urls

    def _pdf_count(self):
        return len(self._pdf_urls())


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
        if not self.tree_html.xpath('//span[@itemprop="ratingValue"]//text()'):
            return None

        return float(self.tree_html.xpath('//span[@itemprop="ratingValue"]//text()')[0])

    def _review_count(self):
        review_rating_list= self.tree_html.xpath('//meta[@itemprop="ratingValue"]/@content')

        if not review_rating_list:
            return 0

        return len(review_rating_list)

    def _max_review(self):
        review_rating_list_text = self.tree_html.xpath('//div[@id="customerReviewContent"]//ul[@id="starRateContainer"]/li/div[contains(@class, "rateBarContainer")]/div[contains(@class,"rateBar")]/text()')
        review_rating_list_int = []

        if not review_rating_list_text:
            return None

        for index in range(5):
            if int(review_rating_list_text[index]) > 0:
                review_rating_list_int.append(5 - index)

        if not review_rating_list_int:
            return None

        return float(max(review_rating_list_int))

    def _min_review(self):
        review_rating_list_text = self.tree_html.xpath('//div[@id="customerReviewContent"]//ul[@id="starRateContainer"]/li/div[contains(@class, "rateBarContainer")]/div[contains(@class,"rateBar")]/text()')
        review_rating_list_int = []

        if not review_rating_list_text:
            return None

        for index in range(5):
            if int(review_rating_list_text[index]) > 0:
                review_rating_list_int.append(5 - index)

        if not review_rating_list_int:
            return None

        return float(min(review_rating_list_int))

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        return self.tree_html.xpath('//div[@id="ctl00_content_divPrice"]//text()')[0].strip()

    def _owned(self):
        if self.tree_html.xpath('//meta[@itemprop="seller"]/@content')[0].strip() == 'Bhinneka.Com':
            return 1
        else:
            return 0

    def _marketplace(self):
        if self.tree_html.xpath('//meta[@itemprop="seller"]/@content')[0].strip() != 'Bhinneka.Com':
            return 1
        else:
            return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################    
    def _categories(self):
        if self._brand().strip().lower() == self.tree_html.xpath('//div[@id="breadcrumb"]/a/text()')[-1].strip().lower():
            return self.tree_html.xpath('//div[@id="breadcrumb"]/a/text()')[1:-1]

        return self.tree_html.xpath('//div[@id="breadcrumb"]/a/text()')[1]

    def _category_name(self):
        return self._categories()[-1]
    
    def _brand(self):
        return self.tree_html.xpath('//a[@id="ctl00_content_lnkBrand"]/@title')[0]

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

        # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \
        "max_review" : _max_review, \
        "min_review" : _min_review, \
        # CONTAINER : SELLERS
        "price" : _price, \
        "owned" : _owned, \
        "marketplace" : _marketplace, \

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
