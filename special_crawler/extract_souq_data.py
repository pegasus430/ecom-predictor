#!/usr/bin/python

import urllib
import re
import sys
import json
import os.path
import urllib, cStringIO
import lxml.html
from io import BytesIO
from PIL import Image
import mmh3 as MurmurHash
from lxml import html
import time
import requests
from lxml.etree import tostring
from itertools import chain
from extract_data import Scraper


class SouqScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://uae.souq.com/ae-en/<product-name-info>/"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        # product features list
        self.features = None
        self.extracted_features = False
        self.images = None
        self.extracted_images = False
        self.videos = None
        self.extracted_videos = False

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://uae.souq.com/ae-en/.+/[iu]/$", self.product_page_url)

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
            itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')[0].strip()

            if itemtype != "product":
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
        product_url = self.tree_html.xpath('//meta[@property="og:url"]/@content')[0].strip()
        start_index = product_url.rfind("-")
        product_id = product_url[start_index + 1:-3]

        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath('//meta[@property="og:title"]/@content')[0].strip()

    def _product_title(self):
        return self.tree_html.xpath('//meta[@property="og:title"]/@content')[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath('//meta[@name="title"]/@content')[0].strip()

    def _model(self):
        """
        *********Not defined in Souq*********
        """
        return None

    def _features(self):
        if self.extracted_features:
            return self.features

        self.extracted_features = True
        feature_html_list = self.tree_html.xpath('//div[contains(@class, "product_text")]'
                                                 '/table//tr')

        if not feature_html_list:
            self.features = None
        else:
            features = []
            regex = re.compile(r'[\n\r\t]')

            for feature_element in feature_html_list:
                feature_raw_text = ''
                feature_raw_text += "".join(feature_element.itertext())
                feature_raw_text = "<tr>" + feature_raw_text + "</tr>"
                feature_raw_text = regex.sub('', feature_raw_text)
                feature_text = ''
                feature_text += "".join(lxml.html.fromstring(feature_raw_text).itertext())
                features.append(feature_text.strip())

            self.features = features

        return self.features

    def _feature_count(self):
        if not self.extracted_features:
            self._features()

        if self.features is None:
            return 0
        else:
            return len(self.features)

    def _description(self):
        description_elements = self.tree_html.xpath('//div[@id="item_attributes"]//li/text()')
        short_description = ''
        short_description += " ".join(str(x) for x in description_elements)
        regex = re.compile(r'[\n\r\t]')
        short_description = regex.sub('', short_description)

        return short_description.strip()

    # extract product long description from its product product page tree
    # ! may throw exception if not found
    # TODO:
    #      - keep line endings maybe? (it sometimes looks sort of like a table and removing them makes things confusing)
    def _long_description(self):
        description_elements = self.tree_html.xpath('//div[contains(@class, "item-desc")]')[0]
        long_description = ''
        long_description += " ".join(description_elements.itertext())
        regex = re.compile(r'[\n\r\t]')
        long_description = regex.sub('', long_description)

        return long_description.strip()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        pass

    def _image_urls(self):
        if self.extracted_images:
            return self.images

        self.extracted_images = True
        self.images = self.tree_html.xpath('//div[@id="thumbs"]/ul[contains(@class, "thumbs")]//img/@src')

        if not self.images:
            self.images = self.tree_html.xpath('//div[@id="item-main-cover"]//'
                                               'img[contains(@class, "img-size-large")]/@src')

        if not self.images:
            self.images = None

        return self.images

    def _image_count(self):
        if not self.extracted_images:
            self._image_urls()

        if self.images is None:
            return 0
        else:
            return len(self.images)

    def _video_urls(self):
        if self.extracted_videos:
            return self.videos

        self.extracted_videos = True
        self.videos = self.tree_html.xpath("//iframe[@allowfullscreen]/@src")

        if not self.videos:
            self.videos = None
        else:
            for index, video_url in enumerate(self.videos):
                if not video_url.strip().startswith("http:"):
                    video_url = "http:" + video_url.strip()
                    self.videos[index] = video_url

        return self.videos

    def _video_count(self):
        if not self.extracted_videos:
            self._video_urls()

        if self.videos is None:
            return 0
        else:
            return len(self.videos)

    # return dictionary with one element containing the PDF
    def _pdf_urls(self):
        """
        *********Not defined in Souq*********
        """
        return None

    def _pdf_count(self):
        """
        *********Not defined in Souq*********
        """
        return 0

    def _webcollage(self):
        """
        *********Not defined in Souq*********
        """
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
        if not self.tree_html.xpath('//div[@class="rating-window-content"]/span/b/text()'):
            return None

        return float(self.tree_html.xpath('//div[@class="rating-window-content"]/span/b/text()')[0])

    def _review_count(self):
        review_rating_list = self.tree_html.xpath('//div[@class="rating-window-content"]/'
                                                  'ul[contains(@class, "total-rating")]/li/'
                                                  'span[@class="fl auto-width"]/text()')

        if not review_rating_list:
            return 0

        review_count = 0
        regex = re.compile(r'[\n\r\t() ]')

        for review in review_rating_list:
            review = regex.sub('', review)
            review_count += int(review)

        return review_count

    def _max_review(self):
        review_rating_list = self.tree_html.xpath('//div[@class="rating-window-content"]/'
                                                  'ul[contains(@class, "total-rating")]/li/'
                                                  'span[@class="fl auto-width"]/text()')

        if not review_rating_list:
            return None

        regex = re.compile(r'[\n\r\t() ]')

        max_rating_value = 0

        for index, review_numbers in enumerate(review_rating_list):
            review_numbers = regex.sub('', review_numbers)

            if int(review_numbers) > 0:
                max_rating_value = 5 - index
                break

        return float(max_rating_value)

    def _min_review(self):
        review_rating_list = self.tree_html.xpath('//div[@class="rating-window-content"]/'
                                                  'ul[contains(@class, "total-rating")]/li/'
                                                  'span[@class="fl auto-width"]/text()')

        if not review_rating_list:
            return None

        regex = re.compile(r'[\n\r\t() ]')

        min_rating_value = 0

        for index, review_numbers in enumerate(reversed(review_rating_list)):
            review_numbers = regex.sub('', review_numbers)

            if int(review_numbers) > 0:
                min_rating_value = index + 1
                break

        return float(min_rating_value)

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath('//div[contains(@class, "vip-cart-row")]//'
                                    'div[contains(@class, "xlarg-price")]/text()')[0].strip()
        currency = self.tree_html.xpath('//div[contains(@class, "vip-cart-row")]//'
                                    'div[contains(@class, "xlarg-price")]/span/text()')[0].strip()

        return price + " " + currency

    def _marketplace(self):
        """
        *********Not defined in Souq*********
        """
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.tree_html.xpath('//ul[@class="headline"]/li[@itemtype="http://data-vocabulary.org/Breadcrumb"]/'
                                          'a[@itemprop="url"]/span[@itemprop="title"]/text()')

        if not categories:
            return None

        return categories

    def _category_name(self):
        return self._categories()[-1]

    def _brand(self):
        return self.tree_html.xpath('//a[@id="brand"]/text()')[0]

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
