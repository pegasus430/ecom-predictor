# -*- coding: utf-8 -*-
#!/usr/bin/python

#!/usr/bin/python

import urllib
import re
import sys
import json

from lxml import html, etree
import lxml.etree as le
import time
import requests
from extract_data import Scraper


class OrientalTradingScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.orientaltrading.com/<product-name>.fltr"
    REVIEW_URL = "http://orientaltrading.ugc.bazaarvoice.com/0713-en_us/{0}/reviews.djs?format=embeddedhtml"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        # whether product has any webcollage media
        # whether product has any webcollage media
        self.review_json = None
        self.review_list = None
        self.is_review_checked = False

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://www\.orientaltrading\.com/.+\.fltr$", self.product_page_url)
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
            itemtype = self.tree_html.xpath('//meta[@property="og:type" and @content="product"]')

            if not itemtype:
                raise Exception()

            if self.tree_html.xpath("//form[@id='multibuy_frm']"):
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
        return self.tree_html.xpath("//form[@id='prod_frm']/input[@id='productId']/@value")[0]

    def _site_id(self):
        return None

    def _status(self):
        return "success"


    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath('//h1[@id="pd-h1-cartridge"]/text()')[0].strip()

    def _product_title(self):
        return self.tree_html.xpath('//h1[@id="pd-h1-cartridge"]/text()')[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath('//h1[@id="pd-h1-cartridge"]/text()')[0].strip()

    def _model(self):
        return None

    def _upc(self):
        return self.tree_html.xpath("//form[@id='prod_frm']/input[@id='sku']/@value")[0]

    def _features(self):
        return None

    def _feature_count(self):
        if self._features():
            return len(self._features())

        return None

    def _model_meta(self):
        return None

    def _description(self):
        description_block = self.tree_html.xpath("//div[@id='product-description-cartridge']/div[@class='pd-text-block']")[0]
        description = description_block.text + ''.join(le.tostring(e) for e in description_block)

        if description.find("&#8226;") > 0:
            short_description = description[:description.find("&#8226;")].strip()
        else:
            short_description = description.strip()

        if short_description:
            return short_description

        return None

    def _long_description(self):
        description_block = self.tree_html.xpath("//div[@id='product-description-cartridge']/div[@class='pd-text-block']")[0]
        description = description_block.text + ''.join(le.tostring(e) for e in description_block)

        if description.find("&#8226;") > 0:
            long_description = description[description.find("&#8226;"):].strip()
        else:
            long_description = None

        if long_description:
            return long_description

        return None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        image_list = self.tree_html.xpath("//div[@id='product-viewer-thumbnails']/a/@href")

        if not image_list:
            image_list = self.tree_html.xpath("//div[@id='product-viewer-current-view']/img/@src")
            image_list = [url.replace("VIEWER_IMAGE_400", "VIEWER_ZOOM") for url in image_list]

        image_list = [url[2:] if url.startswith("//") else url for url in image_list]

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
        review_id = self._find_between(self.page_raw_text, "$BV.ui('rr', 'show_reviews', {productId: '", "'});")
        contents = self.load_page_from_url_with_number_of_retries(self.REVIEW_URL.format(review_id))

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
        return "$" + self._find_between(self.page_raw_text, 'product_list_price: ["', '"]')

    def _price_amount(self):
        return float(self._find_between(self.page_raw_text, 'product_list_price: ["', '"]'))

    def _price_currency(self):
        return "USD"

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):

        if self._site_online() == 0:
            return None

        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        return None

    def _category_name(self):
        return None
    
    def _brand(self):
        return None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces

    def _clean_text(self, text):
        text = text.replace("\n", " ").replace("\t", " ").replace("\r", " ")
       	text = re.sub("&nbsp;", " ", text).strip()

        return re.sub(r'\s+', ' ', text)

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
        "marketplace" : _marketplace, \

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
