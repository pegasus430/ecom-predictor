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

class Cb2Scraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.cb2.com/<product-name>/<product-id>"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        # whether product has any webcollage media
        self.product_json = None
        self.review_json = None
        self.is_review_checked = False
        self.product_json = None

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://www.cb2.com/.*$", self.product_page_url)
        return not not m

    def not_a_product(self):

        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')[0].strip()

        if itemtype != "product":
            return True

        self._extract_product_json()
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _product_id(self):
        arr = re.findall(r'\d+$', self.product_page_url)
        if len(arr) > 0:
            return arr[0]
        return None

    def _extract_product_json(self):

        product_string_id = str(self.product_page_url.rsplit('/', 1)[-1])
        product_non_string_id = str(self._product_id())

        product_json_string = json.loads(requests.get(
            'http://api.bazaarvoice.com/data/reviews.json?apiversion=5.4&passkey=m599ivlm5y69fsznu8h376sxj&Filter=ProductId:' + product_string_id + '&Sort=SubmissionTime:desc&Limit=10&Include=authors,products&Stats=Reviews').content)['Includes']
        product_json_non_string = json.loads(requests.get(
            'http://api.bazaarvoice.com/data/reviews.json?apiversion=5.4&passkey=m599ivlm5y69fsznu8h376sxj&Filter=ProductId:' + product_non_string_id + '&Sort=SubmissionTime:desc&Limit=10&Include=authors,products&Stats=Reviews').content)['Includes']

        if len(product_json_string) > 0:
            product_json = product_json_string
        elif len(product_json_non_string) > 0:
            product_json = product_json_non_string
        else:
            product_json = None
        if not self.product_json:
            self.product_json = product_json

    def _url(self):
        return self.product_page_url

    def _event(self):
        return None

    def _site_id(self):
        arr = re.findall(r'\d+$', self.product_page_url)
        if len(arr) > 0:
            return arr[0]
        return None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_header_name = self.tree_html.xpath('//h1[@class="productHeader"]/text()')
        product_title_name = self.tree_html.xpath('//h1[@class="product-title"]/text()')
        if product_header_name:
            product_name = product_header_name[0].strip()
        else:
            product_name = product_title_name[0].strip()

        return product_name if product_name else None


    def _product_title(self):
        product_title = self._product_name()
        return product_title if product_title else None

    def _title_seo(self):
        title_seo = self._product_name()
        return title_seo if title_seo else None

    def _model(self):
        return None

    def _upc(self):
        return None

    def _features(self):
        return None

    def _feature_count(self):
        features = self._features()

        if features:
            return len(features)

        return 0

    def _description(self):
        tab_discription = ''.join(self.tree_html.xpath("//div[@class='tab-content']//p/text()"))
        p_description = ''.join(self.tree_html.xpath("//p[@class='productDescription']/text()"))

        if tab_discription:
            short_description = tab_discription
        elif p_description:
            short_description = p_description

        if short_description:
            short_description = short_description.replace('\r', '').replace('\n', '').strip()
            return short_description
        return None

    def _long_description(self):
        long_description = self.tree_html.xpath("//ul[@class='productDescriptionList']")
        if long_description:
            long_description = html.tostring(long_description[0]).replace('\r', '').replace('\n', '')
            return long_description
        return None

    def _no_longer_available(self):
        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        image_list = []
        img_info = self.tree_html.xpath("//li[contains(@class, 'thumbnailImage')]//img/@src")
        if img_info:
            for image_url in img_info:
                if 'http:' in image_url:
                    image_url = 'http:' + re.search("http:(.*)web", image_url, re.DOTALL).group(1).replace('?$', '?$web_zoom_furn_hero$')
                elif 'https:' in image_url:
                    image_url = 'https:' + re.search("https:(.*)web", image_url, re.DOTALL).group(1).replace('?$',
                                                                                                           '?$web_zoom_furn_hero$')
                image_list.append(image_url)
        else:
            # single image -> no thumbnails
            image_list = self.tree_html.xpath("//img[contains(@class, 'hwProductImage')]/@src")

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

        product_id = str(self._product_id())
        product_string_id = str(self.product_page_url.rsplit('/', 1)[-1])

        if self.product_json:
            if product_id in self.product_json['Products']:
                average_review = round(self.product_json['Products'][product_id]['ReviewStatistics']['AverageOverallRating'], 1)
            else:
                average_review = round(
                    self.product_json['Products'][product_string_id]['ReviewStatistics']['AverageOverallRating'], 1)
        else:
            return None
        return average_review if average_review else None

    def _review_count(self):
        product_id = str(self._product_id())
        product_string_id = str(self.product_page_url.rsplit('/', 1)[-1])

        if self.product_json:
            if product_id in self.product_json['Products']:
                review_count = self.product_json['Products'][product_id]['ReviewStatistics']['TotalReviewCount']
            else:
                review_count = self.product_json['Products'][product_string_id]['ReviewStatistics']['TotalReviewCount']
        else:
            return None

        return review_count if review_count else None

    def _max_review(self):
        if self._reviews():
            for review in self._reviews():
                if not review[1] == 0:
                    return review[0]

    def _min_review(self):
        if self._reviews():
            for review in self._reviews()[::-1]:  # reverses list
                if not review[1] == 0:
                    return review[0]

    def _reviews(self):

        reviews = []
        product_id = str(self._product_id())
        product_string_id = str(self.product_page_url.rsplit('/', 1)[-1])

        if self.product_json:
            if product_id in self.product_json['Products']:
                ratings_distribution = self.product_json['Products'][product_id]['ReviewStatistics']['RatingDistribution']
            else:
                ratings_distribution = self.product_json['Products'][product_string_id]['ReviewStatistics']['RatingDistribution']
        else:
            return None

        if ratings_distribution:
            for i in range(0, 5):
                ratingFound = False

                for rating in ratings_distribution:
                    if rating['RatingValue'] == i + 1:
                        reviews.append([rating['RatingValue'], rating['Count']])
                        ratingFound = True
                        break

                if not ratingFound:
                    reviews.append([i + 1, 0])

            return reviews[::-1]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price_amount(self):
        price_info = self.tree_html.xpath("//meta[@property='og:price:amount']/@content")[0]
        if price_info:
            price_amount = re.findall(r"[-+]?\d*\.\d+|\d+", price_info.replace(',', ''))[0]
            return price_amount
        return 0

    def _price(self):
        price = self._price_amount()
        if not '$' in price:
            price = '$' + price
        return price

    def _price_currency(self):
        return "USD"

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

    def _marketplace_sellers(self):
        return None

    def _marketplace_lowest_price(self):
        return None

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.tree_html.xpath(
            "//div[@class='breadcrumbs']"
            "//span//a/text()")

        return categories[1:] if categories else None

    def _category_name(self):
        category_name = self._categories()

        return category_name[-1] if category_name else None

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
