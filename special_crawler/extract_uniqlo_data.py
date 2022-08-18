#!/usr/bin/python

import re
import lxml
import lxml.html
import requests
import json

from itertools import groupby

from lxml import html, etree
from extract_data import Scraper

from spiders_shared_code.uniqlo_variants import UniqloVariants


class UniqloScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.uniqlo.com/us/product/<product-name>-<product-id>.html"
    REVIEW_URL = "http://uniqloenus.ugc.bazaarvoice.com/5311-en_us/{}/reviews.djs?format=embeddedhtml"
    PRODUCT_INFO_URL = "http://www.uniqlo.com/us/store/gcx/getProductInfo.do?format=json&product_cd={}"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        # whether product has any webcollage media
        self.review_json = None
        self.price_json = None
        self.failure_type = None
        self.review_list = None
        self.is_review_checked = False
        self.product_json = None
        self.uv = UniqloVariants()
        self.image_list = None
        self.is_image_crawled = False

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """

        m = re.match(r"^http://www.uniqlo.com/us/product/.+\.html$", self.product_page_url)

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
            self._failure_type()

            if self.failure_type:
                self.ERROR_RESPONSE["failure_type"] = self.failure_type
                return True
        except Exception:
            return True

        self._extract_product_json()
        self.uv.setupCH(self.tree_html, self.product_json)
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_product_json(self):
        if self.product_json:
            return

        contents = self.load_page_from_url_with_number_of_retries(self.PRODUCT_INFO_URL.format(self._product_id()))
        self.product_json = json.loads(contents)

    def _canonical_link(self):
        canonical_link = self.tree_html.xpath("//link[@rel='canonical']/@href")[0]

        return canonical_link

    def _url(self):
        return self.product_page_url

    def _product_id(self):
        product_id = self.product_page_url[self.product_page_url.rfind('-') + 1:self.product_page_url.rfind('.')]

        return product_id

    def _failure_type(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')[0]

        if itemtype != "og:product":
            self.failure_type = "Not a product"
            return

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath('//h1[@class="pdp-title" and @itemprop="name"]/text()')[0].strip()

    def _product_title(self):
        return self.tree_html.xpath('//h1[@class="pdp-title" and @itemprop="name"]/text()')[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath('//h1[@class="pdp-title" and @itemprop="name"]/text()')[0].strip()

    def _model(self):
        return None

    def _features(self):
        features = None
        features_html = html.fromstring(self.product_json["material_info"])
        features = features_html.xpath("//li/text()")

        if not features:
            return None

        return features

    def _feature_count(self):
        if self._features():
            return len(self._features())

        return 0

    def _description(self):
        short_description = description = self.tree_html.xpath("//meta[@name='description']/@content")[0]

        if description.find("<br>") > 0:
            short_description = short_description[:short_description.find("<br>")]

        return short_description

    # extract product long description from its product product page tree
    # ! may throw exception if not found
    # TODO:
    #      - keep line endings maybe? (it sometimes looks sort of like a table and removing them makes things confusing)
    def _long_description(self):
        description = self.tree_html.xpath("//meta[@name='description']/@content")[0]
        long_description = None

        if description.find("<br>") > 0:
            long_description = description[description.find("<br>"):]

        return long_description

    def _ingredients(self):
        return None

    def _ingredients_count(self):
        return 0

    def _variants(self):
        return self.uv._variants()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        pass
        
    def _image_urls(self):
        if self.is_image_crawled:
            return self.image_list

        self.is_image_crawled = True

        primary_image = ("http:" + self.tree_html.xpath("//meta[@itemprop='image']/@content")[0]).replace("?$social-share$", "")
        sub_images = primary_image[:primary_image.find("/goods_") + 7] + self._product_id() + "_sub{}"
        thumb_images = primary_image[:primary_image.find("/goods_") + 7] + self._product_id() + "_sub{}?$pdp-thumb$"
        image_list = [primary_image]
        failed_count = 0

        for index in range(1, 20):
            try:
                contents = self.load_page_from_url_with_number_of_retries(thumb_images.format(index))

                if "AQSTa" in contents and len(contents) == 806:
                    failed_count = failed_count + 1

                    if failed_count > 2:
                        break

                    continue

                image_list.append(sub_images.format(index))
            except:
                break

        if not image_list:
            self.image_list = None
        else:
            self.image_list = image_list

        return self.image_list

    def _image_count(self):
        if not self._image_urls():
            return 0

        return len(self.image_list)

    def _video_urls(self):
        return None

    def _video_count(self):
        return 0

    # return dictionary with one element containing the PDF
    def _pdf_urls(self):
        return None

    def _pdf_count(self):
        return 0

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

        contents = self.load_page_from_url_with_number_of_retries(self.REVIEW_URL.format(self._product_id()))

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
        return "$" + str(self.product_json["l2_goods_list"][0]["sales_price"])

    def _price_amount(self):
        return float(self.product_json["l2_goods_list"][0]["sales_price"])

    def _price_currency(self):
        return "USD"

    def _marketplace(self):
        return 0

    def _site_online(self):
        return 1

    def _in_stores(self):
        if self.tree_html.xpath("//img[@alt='Online_Exclusive.gif']"):
            return 0

        return 1

    def _site_online_out_of_stock(self):
        if int(self.product_json['stock_cnt_l1']) > 0:
            return 0

        return 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################    
    def _categories(self):
        return self.tree_html.xpath("//ul[@class='breadcrumb-component']/li[@class='breadcrumb-item']/a/text()")

    def _category_name(self):
        return self._categories()[-1]

    def _brand(self):
        return None

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
        "ingredients": _ingredients, \
        "ingredient_count": _ingredients_count,
        "variants": _variants, \

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
        "marketplace" : _marketplace, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "in_stores" : _in_stores, \

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
