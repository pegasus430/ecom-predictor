#!/usr/bin/python

import urllib
import re
import sys
import json

from lxml import html, etree
import time
import requests
from extract_data import Scraper

class SchuhScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.schuh.co.uk/p/<product-name>/<product-id>"

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://www.schuh.co.uk/.*?$", self.product_page_url)
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
            itemtype = self.tree_html.xpath('//div[@itemtype="http://schema.org/Product"]')

            if not itemtype:
                raise Exception()

        except Exception:
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
        canonical_link = self.tree_html.xpath('//link[@rel="canonical"]/@href')
        return canonical_link

    def _url(self):
        return self.product_page_url

    def _product_id(self):
        product_id = self.tree_html.xpath('//span[@itemprop="sku"]/text()')[0]
        return product_id

    def _site_id(self):
        product_id = self.tree_html.xpath('//span[@itemprop="sku"]/text()')[0]
        return product_id

    def _status(self):
        return "success"

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.tree_html.xpath('//link[@rel="alternate"]/@title')[0]

    def _product_title(self):
        return self.tree_html.xpath('//link[@rel="alternate"]/@title')[0]

    def _title_seo(self):
        return self.tree_html.xpath('//link[@rel="alternate"]/@title')[0]

    def _features(self):
        features = self.tree_html.xpath('//div[@id="itemInfo"]/div//text()')
        values = []
        features_list = []

        for i in features:
            if i != ' ':
                values.append(i)

        for i in range(0, len(values) - 1, 2):
            features_list.append(values[i].strip() + " " + values[i + 1].strip())

        return features_list

    def _feature_count(self):
        if self._features():
            return len(self._features())

        return None

    def _description(self):
        desc = self.tree_html.xpath('//div[@itemprop="description"]/text()')
        short_description = desc[0].strip()
        return short_description

    def _long_description(self):
        desc = self.tree_html.xpath('//div[@itemprop="description"]')[0]
        after_ul = self.tree_html.xpath('//div[@id="itemInfo"]/div')
        after_ul_desc = ""
        long_description = ""
        long_description_start = False

        for description_item in desc:
            if description_item.tag == "ul":
                long_description_start = True

            if long_description_start:
                long_description = long_description + html.tostring(description_item)

        long_description = long_description.strip()

        for i in after_ul:
            after_ul_desc += html.tostring(i)

        # after_ul_desc = after_ul_desc.strip()
        long_description += after_ul_desc

        if long_description:
            return long_description

        return None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        images = self.tree_html.xpath('//div[@id="swipe"]//ul/li/img/@data-mob-src')
        image_list = []

        first_img = self.tree_html.xpath('//div[@id="swipe"]//ul/li/span/img/@data-mob-src')[0]
        image_list.append(first_img)

        for media_item in images:
            image_list.append(media_item)

        if image_list:
            return image_list

        return None

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    def _keywords(self):
        return self.tree_html.xpath('//meta[@id="metaKeywords"]/@content')[0]

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        average_review = self.tree_html.xpath('//meta[@itemprop="ratingValue"]/@content')[0]
        assessment = float(average_review)
        if assessment:
            return assessment

    def _review_count(self):
        count = self.tree_html.xpath('//div[@id="itemRating"]/a/text()')[1]
        count_int = re.search('\d+', count)

        if count_int:
            return int(count_int.group(0))

    def _max_review(self):
        if self._review_count() == 0:
            return None

        for i, review in enumerate(self._reviews()):
            if review[1] > 0:
                return 5 - i

    def _min_review(self):
        if self._review_count() == 0:
            return None

        for i, review in enumerate(reversed(self._reviews())):
            if review[1] > 0:
                return i + 1

    def _reviews(self):
        if self._review_count() > 0:
            mark = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            id = self._product_id()
            max_num = self._review_count()
            startReview = 6
            reviews = ""

            first_five = self.tree_html.xpath('//ul[@id="reviews"]/li/div[1]/div/div/@data-icon')

            for i in first_five:
                if i == "*****":
                    mark[5] += 1
                elif i == "****$":
                    mark[4] += 1
                elif i == "****#":
                    mark[4] += 1
                elif i == "***##":
                    mark[3] += 1
                elif i == "**###":
                    mark[2] += 1
                elif i == "*####":
                    mark[1] += 1

            h = {'content-type': 'application/json'}

            if max_num > 100:
                max_num = 100

            for i in xrange(startReview, max_num, 10):
                data = {"iCode": id, "numReviews": i + 9, "startReview": i}
                reviews += requests.post('http://www.schuh.co.uk/Service/getMoreReviews', headers=h, timeout=5, data=json.dumps(data)).text

            other_makrs = re.findall(r'\w{4}-\w{4}=\\"(\*{1,5})[#\$]*\\"', reviews)

            for i in other_makrs:
                mark[len(i)] += 1

            reviews_list = [[item, mark[item]] for item in sorted(mark.keys(),
                                                                  reverse=True)]
            return reviews_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        return self.tree_html.xpath('//span[@id="price"]/text()')[0]

    def _price_amount(self):
        price = self.tree_html.xpath('//span[@id="price"]/text()')[0]
        price_int = re.search('\d{1,}.\d{2}', price)
        return float(price_int.group(0))

    def _price_currency(self):
        return "GBP"

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        return self.tree_html.xpath('//div[@itemprop="breadcrumb"]/a[last()]/text()')[0]

    def _category_name(self):
        return self.tree_html.xpath('//div[@itemprop="breadcrumb"]/a[last()]/text()')[0]

    def _brand(self):
        brands = self.tree_html.xpath('//span[@id="itemLogo"]//img/@title')
        brand = brands[0].replace('logo', '')
        return brand.strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "url" : _url, \
        "product_id" : _product_id, \
        "site_id" : _site_id, \
        "status" : _status, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "features" : _features, \
        "feature_count" : _feature_count, \
        "description" : _description, \
        "long_description" : _long_description, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count" : _image_count, \
        "image_urls" : _image_urls, \
        "keywords" : _keywords, \
        "canonical_link" : _canonical_link, \

        # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \
        "reviews" : _reviews, \
        "max_review" : _max_review, \
        "min_review" : _min_review, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "price_amount" : _price_amount, \
        "price_currency" : _price_currency, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "category_name" : _category_name, \
        "brand" : _brand, \
    }
