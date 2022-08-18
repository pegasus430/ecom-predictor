#!/usr/bin/python

import urllib
import re
import sys
import json

from lxml import html, etree
import time
import requests
from extract_data import Scraper


class HalfordsScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.halfords.com/<category-name>/<product-name>"
    REVIEW_URL = "http://halfords.ugc.bazaarvoice.com/4028-redes/{0}/reviews.djs?format=embeddedhtml"
    IMAGE_URL = "http://i1.adis.ws/s/washford/{0}_is.js"
    VIDEO_URL = "http://i1.adis.ws/v/washford/video_product_{0}.js"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        # whether product has any webcollage media
        self.product_json = None
        # whether product has any webcollage media
        self.review_json = None
        self.review_list = None
        self.is_review_checked = False
        self.image_list = None
        self.is_image_checked = False
        self.video_list = None
        self.is_video_checked = False

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://www.halfords.com/.*?$", self.product_page_url)
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
            itemtype = self.tree_html.xpath('//div[@id="container" and @class="productdetails"]')

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
        product_id = self._find_between(html.tostring(self.tree_html), "productId = '", "'")
        return product_id

    def _site_id(self):
        product_id = self._find_between(html.tostring(self.tree_html), "productId = '", "'")
        return product_id

    def _status(self):
        return "success"






    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath("//meta[@property='og:title']/@content")[0].strip()

    def _product_title(self):
        return self.tree_html.xpath("//meta[@property='og:title']/@content")[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath("//meta[@property='og:title']/@content")[0].strip()

    def _model(self):
        return None

    def _upc(self):
        return None

    def _features(self):
        return None

    def _feature_count(self):
        return 0

    def _model_meta(self):
        return None

    def _description(self):
        return self.tree_html.xpath("//meta[@property='og:description']/@content")[0].strip()

    def _long_description(self):
        long_description_content = self.tree_html.xpath("//ul[@id='productFeatures']")[0].text_content().strip()

        long_description_content = re.sub('\\n+', ' ', long_description_content).strip()
        long_description_content = re.sub('\\t+', ' ', long_description_content).strip()
        long_description_content = re.sub(' +', ' ', long_description_content).strip()

        return long_description_content

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        if self.is_image_checked:
            return self.image_list

        self.is_image_checked = True

        productImageName = self._find_between(html.tostring(self.tree_html), "partNumber = '", "'")

        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)
        contents = s.get(self.IMAGE_URL.format(productImageName), headers=h, timeout=5).text.strip()

        image_items = json.loads(contents[7:-2])["items"]
        image_urls = []

        for image in image_items:
            image_urls.append(image["src"])

        if image_urls:
            self.image_list = image_urls
            return self.image_list

        return None

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    def _video_urls(self):
        if self.is_video_checked:
            return self.video_list

        self.is_video_checked = True

        productImageName = self._find_between(html.tostring(self.tree_html), "partNumber = '", "'")

        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)
        contents = s.get(self.VIDEO_URL.format(productImageName), headers=h, timeout=5).text.strip()

        video_items = json.loads(contents[10:-2])

        if "media" not in video_items:
            return None

        self.video_list = [video_items["media"][0]["src"]]

        return self.video_list

    def _video_count(self):
        videos = self._video_urls()

        if videos:
            return len(videos)

        return 0

    def _pdf_urls(self):
        pdf_url_list = re.findall(r'(http://.*?\.pdf)', html.tostring(self.tree_html))

        if pdf_url_list:
            return pdf_url_list

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
        if self._review_count() == 0:
            return None

        average_review = round(float(self.review_json["jsonData"]["attributes"]["avgRating"]), 1)

        if str(average_review).split('.')[1] == '0':
            return int(average_review)
        else:
            return float(average_review)

    def _review_count(self):
        self._reviews()

        if not self.review_json:
            return 0

        return int(self.review_json["jsonData"]["attributes"]["numReviews"])

    def _max_review(self):
        if self._review_count() == 0:
            return None

        for i, review in enumerate(self.review_list):
            if review[1] > 0:
                return 5 - i

    def _min_review(self):
        if self._review_count() == 0:
            return None

        for i, review in enumerate(reversed(self.review_list)):
            if review[1] > 0:
                return i + 1

    def _reviews(self):
        if self.is_review_checked:
            return self.review_list

        self.is_review_checked = True

        ppn = self._find_between(html.tostring(self.tree_html), "ppn = '", "'")

        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)
        contents = s.get(self.REVIEW_URL.format(ppn), headers=h, timeout=5).text

        try:
            start_index = contents.find("webAnalyticsConfig:") + len("webAnalyticsConfig:")
            end_index = contents.find(",\nwidgetInitializers:initializers", start_index)

            self.review_json = contents[start_index:end_index]
            self.review_json = json.loads(self.review_json)
        except:
            self.review_json = None

        review_html = html.fromstring(re.search('"BVRRSecondaryRatingSummarySourceID":" (.+?)"},\ninitializers={', contents).group(1))
        reviews_by_mark = review_html.xpath("//*[contains(@class, 'BVRRHistAbsLabel')]/text()")
        reviews_by_mark = reviews_by_mark[:5]
        review_list = [[5 - i, int(re.findall('\d+', mark)[0])] for i, mark in enumerate(reviews_by_mark)]

        if not review_list:
            review_list = None

        self.review_list = review_list

        return self.review_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price_text = self.tree_html.xpath("//div[@id='priceAndLogo']/h2/text()")[0].strip()
        price_text = re.sub('\\n+', '', price_text).strip()
        price_text = re.sub('\\t+', '', price_text).strip()
        price_text = re.sub(' +', '', price_text).strip()
        return price_text

    def _price_amount(self):
        return float(re.findall(r"\d*\.\d+|\d+", self._price().replace(",", ""))[0])

    def _price_currency(self):
        return self._find_between(html.tostring(self.tree_html), 'currency: "', '"')

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
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
        return self.tree_html.xpath("//nav[@id='breadcrumb']//li/a/text()")[1:]

    def _category_name(self):
        return self._categories()[-1]

    def _brand(self):
        return self.tree_html.xpath("//span[@class='brand']/text()")[0].strip()



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
