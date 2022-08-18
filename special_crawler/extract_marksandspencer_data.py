# -*- coding: utf-8 -*-#

#!/usr/bin/python

import urllib
import re
import sys
import json

from lxml import html, etree
import time
import requests
from extract_data import Scraper


class MarksAndSpencerScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.marksandspencer.com/<product-name>/p/p[0-9]+$"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.review_list = None
        self.average_review = None
        self.max_review = None
        self.min_review = None
        self.review_count = 0
        self.is_review_checked = False


    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://www.marksandspencer.com/.*/p/p[0-9]+$", self.product_page_url)
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
            itemtype = self.tree_html.xpath('//ul[@id="product-detail-page"]/@itemtype')[0].strip()

            if itemtype != "http://schema.org/Product":
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
        product_id = self.product_page_url.split('/')[-1]

        return product_id

    def _site_id(self):
        return self.tree_html.xpath("//p[@class='code']/text()")[0].strip()

    def _status(self):
        return "success"






    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath('//h1[@itemprop="name"]')[0].text_content().strip()

    def _product_title(self):
        return self.tree_html.xpath('//h1[@itemprop="name"]')[0].text_content().strip()

    def _title_seo(self):
        return self.tree_html.xpath('//h1[@itemprop="name"]')[0].text_content().strip()

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
        short_description = self.tree_html.xpath("//p[@class='product-description']")[0].text_content().strip()

        if not short_description:
            return None

        return short_description

    def _long_description(self):
        long_description = self.tree_html.xpath("//div[@data-panel-id='productInformation']//div[contains(@class, 'subcontent')]")[0].text_content().strip()

        if not long_description:
            return None

        return long_description



    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        link = "http:" + self.tree_html.xpath("//div[@id='generateUniqueIdHere']/@data-default-imageset")[0]
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)
        contents = s.get(link, headers=h, timeout=5).text

        image_urls_json = json.loads("{" + re.search('{(.+?)}', contents).group(1) + "}")
        image_urls = image_urls_json["IMAGE_SET"].split(",")

        image_urls = ["http://asset1.marksandspencer.com/is/image/" + url.split(";")[0] for url in image_urls]

        if not image_urls:
            return None

        return image_urls

    def _image_count(self):
        image_urls = self._image_urls()

        if not image_urls:
            return 0

        return len(image_urls)

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
        self._reviews()

        return self.average_review

    def _review_count(self):
        self._reviews()

        return self.review_count

    def _max_review(self):
        self._reviews()

        return self.max_review

    def _min_review(self):
        self._reviews()

        return self.min_review

    def _reviews(self):
        if self.is_review_checked:
            return self.review_list

        self.is_review_checked = True

        link = ("http://reviews.marksandspencer.com/2050-en_gb/{id}/reviews.djs?format=embeddedhtml").format(id=self._product_id())
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)
        contents = s.get(link, headers=h, timeout=5).text

        review_html = html.fromstring(re.search('var materials=\{"BVRRSecondaryRatingSummarySourceID":"(.+?),"BVRRSourceID":"', contents).group(1))
        self.review_count = int(re.findall('\d+', review_html.xpath("//span[contains(@class, 'BVRRRatingSummaryHeaderCounterValue')]/text()")[0])[0])

        rbs = review_html.xpath(
            "//span[contains(@class, 'BVRRHistAbsLabel')]/text()"
        )[:5]
        rbs.reverse()
        review_list = {}

        if rbs:
            for i in range(5, 0, -1):
                review_list[i] = int(rbs[i-1].replace(
                    "\n", "").replace("\t", "").replace("\\n", ""))

                if review_list[i] > 0 and (not self.max_review or self.max_review < i):
                    self.max_review = i

                if review_list[i] > 0 and (not self.min_review or self.min_review > i):
                    self.min_review = i

        if not review_list:
            return None

        self.review_list = [[key, review_list[key]] for key in review_list]
        self.average_review = "%.1f" % float(re.findall("avgRating\"\:(\d*\.\d+|\d+)", contents.replace(",", ""))[0])

        return self.review_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = json.loads(re.search('\{"price":"&pound;(.+?)","prevPrice":"', html.tostring(self.tree_html)).group(1))
        return '£' + str(price)

    def _price_amount(self):
        price = json.loads(re.search('\{"price":"&pound;(.+?)","prevPrice":"', html.tostring(self.tree_html)).group(1))
        return price

    def _price_currency(self):
        return "GBP"

    def _in_stores(self):
        return 1

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
        categories = self.tree_html.xpath("//ul[@class='breadcrumb']/li/a/text()")
        categories = [category.strip() for category in categories]

        return categories

    def _category_name(self):
        categories = self._categories()

        return categories[-1]

    def _brand(self):
        return None


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
        "reviews" : _reviews,

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
