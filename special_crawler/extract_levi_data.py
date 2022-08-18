#!/usr/bin/python

import urllib
import re
import sys
import json
import mechanize
import cookielib
from lxml import html, etree
import time
import requests
from extract_data import Scraper
from spiders_shared_code.levi_variants import LeviVariants

class LeviScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.levi.com/US/en_US/<category-name>/p/<product-id>"
    REVIEW_URL = "http://levistrauss.ugc.bazaarvoice.com/9090-en_us/{0}/reviews.djs?format=embeddedhtml"
    ADD_REVIEW_URL = "http://levistrauss.ugc.bazaarvoice.com/9090-en_us/{0}/reviews.djs?format=embeddedhtml&page={1}&"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        # whether product has any webcollage media
        self.product_json = None
        self.buy_stack_json = None
        # whether product has any webcollage media
        self.review_json = None
        self.rev_list = None
        self.is_review_checked = False
        self.lv = LeviVariants()
        self._set_proxy()

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://www.levi.com/US/en_US/(.*/)?p/.*$", self.product_page_url)
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
            self.lv.setupCH(self.tree_html)
        except:
            pass

        try:
            if self._no_longer_available():
                return False

            itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')[0].strip()

            if itemtype != "product":
                raise Exception()

            self._extract_product_json()
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
            product_json_text = self._find_between(" " . join(self.tree_html.xpath("//script[@type='text/javascript']/text()")), "var pageData = ", ";\r")
            self.product_json = json.loads(product_json_text)
        except:
            try:
                product_json_text = self._find_between(" " . join(self.tree_html.xpath("//script[@type='text/javascript']/text()")), "var pageData = ", ";\n")
                product_json_text = product_json_text.replace("getjsonTrackingObject({", "{")
                product_json_text = product_json_text.replace("})", "}")
                self.product_json = json.loads(product_json_text)
            except:
                self.product_json = None

        try:
            # buy_stack_json_text = self._find_between(" " . join(self.tree_html.xpath("//script[@type='text/javascript']/text()")), "var buyStackJSON = '", "'; var productCodeMaster =").replace("\'", '"').replace('\\\\"', "")
            buy_stack_json_text = " " . join(self.tree_html.xpath("//script[@type='text/javascript']/text()"))
            buy_stack_json_text = re.findall(r'var buyStackJSON = \'(\{.*?\})\';', buy_stack_json_text)
            if len(buy_stack_json_text) > 0:
                self.buy_stack_json = json.loads(buy_stack_json_text[0].replace("\'", '"').replace('\\\\"', ""))
            else:
                self.buy_stack_json = None
        except:
            self.buy_stack_json = None

    def _canonical_link(self):
        canonical_link = self.tree_html.xpath("//link[@rel='canonical']/@href")[0]

        return canonical_link

    def _url(self):
        return self.product_page_url

    def _event(self):
        return None

    def _product_id(self):
        arr = re.findall(r'p/(\d+)', self.product_page_url)
        if len(arr) > 0:
            return arr[0]
        return None
        # return self.product_json["product"][0]["product_id"]

    def _site_id(self):
        arr = re.findall(r'p/(\d+)', self.product_page_url)
        if len(arr) > 0:
            return arr[0]
        return None
        # return self.product_json["product"][0]["product_id"]

    def _status(self):
        return "success"

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath('//h1[@itemprop="name"]/text()')[0]

    def _product_title(self):
        return self.tree_html.xpath('//h1[@itemprop="name"]/text()')[0]

    def _title_seo(self):
        return self.tree_html.xpath('//h1[@itemprop="name"]/text()')[0]

    def _model(self):
        return self.tree_html.xpath("//meta[@itemprop='model']/@content")[0]

    def _upc(self):
        return None

    def _features(self):
        features_string = ""

        for colorid in self.buy_stack_json["colorid"]:
            features_string = self.buy_stack_json["colorid"][colorid]["fabric"]
            break

        features = features_string.split("<br>")

        if features:
            return features

        return None

    def _feature_count(self):
        features = self._features()

        if features:
            return len(features)

        return 0

    def _description(self):
        short_description = self.tree_html.xpath("//meta[@property='og:description']/@content")[0].strip()

        if short_description:
            return short_description

        return None

    def _long_description(self):
        for colorid in self.buy_stack_json["colorid"]:
            return self.buy_stack_json["colorid"][colorid]["fabric"]

        return None

    def _variants(self):
        return self.lv._variants()

    def _swatches(self):
        return self.lv._swatches()

    def _no_longer_available(self):
        nla = self.tree_html.xpath('//div[@class="rich-media-para"]/h2/text()')

        if nla and nla[0] == 'This product is no longer available.':
            return 1
        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        image_urls = []

        for url in self.buy_stack_json["colorid"][self._product_id()]["altViews"]:
            image_urls.append(self.buy_stack_json["colorid"][self._product_id()]["imageURL"] + url)

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
        return 0

    def _pdf_urls(self):
        return None

    def _pdf_count(self):
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
        if self._review_count() == 0:
            return None

        average_review = round(float(self.review_json["jsonData"]["attributes"]["avgRating"]), 1)

        if str(average_review).split('.')[1] == '0':
            return int(average_review)
        else:
            return float(average_review)

    def _review_count(self):
        self._reviews()

        if not self.glob_review_count:
            return 0

        return self.glob_review_count

    def _max_review(self):
        if self._review_count() == 0:
            return None

        for i, review in enumerate(self.rev_list):
            if review[1] > 0:
                return 5 - i

    def _min_review(self):
        if self._review_count() == 0:
            return None

        for i, review in enumerate(reversed(self.rev_list)):
            if review[1] > 0:
                return i + 1

    def _reviews(self):
        if self.is_review_checked:
            return self.rev_list

        self.is_review_checked = True

        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)
        contents = s.get(self.REVIEW_URL.format(self._product_id()), headers=h, timeout=5).text

        try:
            start_index = contents.find("webAnalyticsConfig:") + len("webAnalyticsConfig:")
            end_index = contents.find(",\nwidgetInitializers:initializers", start_index)

            self.review_json = contents[start_index:end_index]
            self.review_json = json.loads(self.review_json)
        except:
            self.review_json = None
            return None

        offset = 0
        number_of_passes = int(self.review_json["jsonData"]["attributes"]["numReviews"])

        real_count = []
        real_count += re.findall(r'<div class=\\"BVRRHeaderPagingControls\\">'
                                 r'SHOWING \d+-\d+ OF (\d+)', contents)

        review_count = self.glob_review_count = 0

        if real_count:
            review_count = int(real_count[0])
            self.glob_review_count = int(real_count[0]) # for transfer to another method

        if review_count > 0:
            for index, i in enumerate(xrange(1, review_count + 1, 30)):
                contents += s.get(self.ADD_REVIEW_URL.
                                  format(self._product_id(), index + 2),
                                  headers=h, timeout=5).text

            marks = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

            while number_of_passes > 0:
                ratingValue = self._find_between(contents, '<span itemprop=\\"ratingValue\\" class=\\"BVRRNumber BVRRRatingNumber\\">', "<\\/span>", offset).strip()

                if offset == 0:
                    offset = contents.find('<span itemprop=\\"ratingValue\\" class=\\"BVRRNumber BVRRRatingNumber\\">') + len('<span itemprop=\\"ratingValue\\" class=\\"BVRRNumber BVRRRatingNumber\\">')
                    continue

                if not ratingValue:
                    break

                offset = contents.find('<span itemprop=\\"ratingValue\\" class=\\"BVRRNumber BVRRRatingNumber\\">', offset) + len('<span itemprop=\\"ratingValue\\" class=\\"BVRRNumber BVRRRatingNumber\\">')

                if ratingValue.endswith('0'):
                    ratingValue = int(float(ratingValue))
                    marks[ratingValue] += 1

                number_of_passes -= 1

            self.rev_list = [[item, marks[item]] for item in sorted(marks.keys(),
                                                                    reverse=True)]
        return self.rev_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        return "$" + str(self.product_json["product"][0]["online_price"])

    def _price_amount(self):
        return float(self.product_json["product"][0]["online_price"])

    def _price_currency(self):
        return "USD"

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        out_of_stock = 1

        for sku in self.buy_stack_json["sku"]:
            if self.buy_stack_json["sku"][sku]["stock"] > 0:
                out_of_stock = 0
                break

        return out_of_stock

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
        return [self.product_json["page"]["page_department"], self.product_json["page"]["page_category"]]

    def _category_name(self):
        return self.product_json["page"]["page_category"]

    def _brand(self):
        return self.product_json["page"]["brand"]


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
        "description" : _description, \
        "long_description" : _long_description, \
        "variants": _variants, \
        "swatches": _swatches, \
        "no_longer_available": _no_longer_available, \

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
