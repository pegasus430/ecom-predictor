#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import urllib2

from lxml import html
import requests
import math
import json

from extract_data import Scraper
from requests.auth import HTTPBasicAuth


class MotherCareScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.mothercare.com/" \
                          "<product-name>"

    REVIEW_URL = "http://www.mothercare.com/on/demandware.store/" \
                  "Sites-MCENGB-Site/default/ReevooReview-Show?" \
                  "reevoo_page=1&format=&source=&pwr=&" \
                  "pid={0}#reevoo_embedded_reviews"


    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://www.mothercare.com/.*?$", self.product_page_url)
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
            itemtype = self.tree_html.xpath('//div[@class="pt_product"]')

            if not itemtype:
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
        prod_id = self.tree_html.xpath('//span[@class="codevalue"]/text()')
        if prod_id:
            return prod_id[0]

        return None

    def _site_id(self):
        return None

    def _status(self):
        return "success"

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        name = self.tree_html.xpath('//h1[@class="productname"]/text()')[0]
        return name

    def _product_title(self):
        return self.tree_html.xpath('//title/text()')[0]

    def _features(self):
        th_text = self.tree_html.xpath('//div[@id="productSpecsTab"]//table/tr/th/text()')
        td_text = self.tree_html.xpath('//div[@id="productSpecsTab"]//table/tr/td/text()')

        if th_text and td_text:
            features_list = []
            th = self.exclude_repetition(th_text)
            td = self.exclude_repetition(td_text)

            for i in range(len(th)):
                features_list.append(th[i].strip() + ": " + td[i].strip())

            return features_list

    def _feature_count(self):
        if self._features():
            return len(self._features())

        return None

    def _description(self):
        desc = self.tree_html.xpath('//div[@class="productdescription bundle-description"]/p//text()')

        if desc:
            desc_line = ""
            for i in desc:
                desc_line += i.strip() + " "

            return desc_line

        return None

    def _long_description(self):
        desc = self.tree_html.xpath('//div[@id="pdpTab1"]//text()')

        if desc:
            desc_line = ""
            for i in desc:
                desc_line += i.strip() + " "

            return desc_line

        return None

    def _click_and_collect(self):
        sample = self.tree_html.xpath('//li[@class="collection instore '
                                      'statusmessage available"]')
        if sample:
            return 1

        return None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    ##########################################

    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        IMG_JSON = 'http://mothercare.scene7.com/is/image/MothercareASE/' \
                   '{0}_MMSET?req=set,json,UTF-8&labelkey=label&id=' \
                   '143162988&handler=s7sdkJSONResponse'

        IMG_URL = 'http://mothercare.scene7.com/is/image/{0}'

        prod_id = self._product_id()
        id = 'l' + prod_id.lower()
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)

        contents = s.get(IMG_JSON.format(id), headers=h,
                         timeout=5).text

        sample = contents.split(',')
        image_list_str = []
        img_list = []

        for i in sample:
            image_list_str += re.findall(r'"n":"(MothercareASE/.*)"', i)

        for index, i in enumerate(image_list_str):
            if index > 0 and index % 2 == 0 and len(i) <= 23:
                img_list.append(IMG_URL.format(i))

        if img_list:
            return img_list

        return None

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    def _htags(self):
        htags_dict = {}
        htags_dict["h1"] = map(lambda t: self._clean_text(t),
                               self.tree_html.xpath("//h1//text()"
                                                    "[normalize-space()!='']"))
        htags_dict["h2"] = map(lambda t: self._clean_text(t),
                               self.tree_html.xpath("//h2//text()"
                                                    "[normalize-space()!='']"))
        return htags_dict

    def _keywords(self):
        keywords = self.tree_html.xpath('//meta[@name="keywords"]/@content')[0]
        if keywords:
            return keywords

        return None

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################
    def _average_review(self):
        if self._review_count() == 0:
            return None

        content = self.basic_request()
        var = re.findall(r'Score is (\d.\d+) out of 10 from (\d+) reviews',
                         content)
        average_reviews = float(var[0][0])

        if average_reviews:
            return average_reviews

    def _max_review(self):
        if self._review_count() == 0:
            return None

        for i, review in enumerate(self._reviews()):
            if review[1] > 0:
                return 10 - i

    def _min_review(self):
        if self._review_count() == 0:
            return None

        for i, review in enumerate(reversed(self.reviews_list)):
            if review[1] > 0:
                return i + 1

    def _review_count(self):
        content = self.basic_request()

        var = re.findall(r'Score is (\d.\d+) out of 10 from (\d+) reviews',
                         content)
        reviews_count = int(var[0][1])
        if reviews_count:
            return reviews_count

        return 0

    def _reviews(self):
        """
        If reviewer left no comment it is impossible to obtain the estimation.
        On this number of assessments is different from the number of reviews.
        """

        marks = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0}

        content = self.basic_request()
        var = re.findall(r'Score is (\d.\d+) out of 10 from (\d+) reviews',
                         content)
        reviews_count = float(var[0][1])

        if reviews_count > 10:
            content += self.additional_requests(reviews_count)
            marks = self.count_of_ratings(content, marks)
        else:
            marks = self.count_of_ratings(content, marks)

        self.reviews_list = [[item, marks[item]] for item in
                             sorted(marks.keys(), reverse=True)]

        if self.reviews_list:
            return self.reviews_list

        return None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        currency = {"GBP": u"£", "USD": "$"}
        return currency[self._price_currency()] + str(self._price_amount())

    def _price_amount(self):
        script = self.tree_html.xpath('//script[contains(text(), "sale")]')
        price = []
        for i in script:
            val = html.tostring(i)
            price += re.findall(r'"sale" : (\d*\.\d+|\d+)', val.replace(",", ""))

        if price:
            return float(price[0])

        return None

    def _price_currency(self):
        script = self.tree_html.xpath('//script[contains(text(), "currencyCode")]'
                                      '/text()')
        currency = []
        for i in script:
            currency = re.findall(r'"currencyCode" : "(\w+)"', i)

        if currency:
            return currency[0]

        return None

    def _site_online_in_stock(self):
        in_stock = self.tree_html.xpath('//div[@class="productsetselection '
                                        'bundle-selection"]'
                                        '//span[@class="inStock"]/text()')

        if not in_stock:
            in_stock = self.tree_html.xpath('//h2 [@class="availability"]'
                                            '/span[2]//text()')
        if 'In stock' in in_stock:
            return 1

        return 0

    def _site_online(self):
        return 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath('//div[@class="breadcrumb"]'
                                          '//a/text()')
        if categories:
            return categories[1:]

        return None

    def _category_name(self):
        category_name = self._categories()[-1]

        if category_name:
            return category_name

        return None

    def _brand(self):
        brand = self.tree_html.xpath('//p[@class="productbrand"]'
                                     '//span[@itemprop="name"]/text()')[0]

        if brand:
            return brand

        return None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    def prod_id(self):
        script = self.tree_html.xpath('//script[contains(text(), "productID")]'
                                      '/text()')
        product_id = []
        var = re.findall(r'"productID":"(\d+)"', script[0])

        if len(var) > 0:
            product_id = var[0]

        return product_id

    # clean text inside html tags - remove html entities, trim spaces
    def _clean_text(self, text):
        return re.sub("&nbsp;", " ", text).strip()

    def basic_request(self):
        """
        Sending a request for the collection of reviews_count, average_reviews
        and reviews
        """
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)

        contents = s.get(self.REVIEW_URL.format(self.prod_id()), headers=h,
                         timeout=5).text

        return contents

    def additional_requests(self, reviews_count):
        """
        Sending multiple additional requests for data collection from the
        reviews
        """
        content = ''
        ADD_REVIEW_URL = "http://www.mothercare.com/on/demandware.store/" \
                  "Sites-MCENGB-Site/default/ReevooReview-Show?" \
                  "reevoo_page={0}&format=&source=&pwr=&" \
                  "pid={1}#reevoo_embedded_reviews"


        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)

        end = int(math.ceil(reviews_count / 10))
        for i in range(2, end + 1):
            content += s.get(ADD_REVIEW_URL.format(i, self.prod_id()),
                             headers=h, timeout=5).text

        return content

    def count_of_ratings(self, content, marks):
        """
        Count of ratings and entering them in the dictionary
        """
        mark = []

        html_contents = html.fromstring(content)
        list_of_assessments = html_contents.xpath('//div[@class='
                                                  '"overall_score_stars"]'
                                                  '/text()')
        for i in list_of_assessments:
            mark += re.findall(r'(\d+) out', i)

        for i in mark:
            marks[int(i)] += 1

        return marks

    def exclude_repetition(self, sample):
        """
        Removes duplicate values from the list
        """
        index_stop = len(sample) / 2
        sample = sample[:index_stop]
        return sample


    ##########################################
    ################ RETURN TYPES
    ##########################################
    """
    dictionaries mapping type of info to be extracted to the method that
    does it also used to define types of data that can be requested to
    the REST service
    """

    DATA_TYPES = {
        # CONTAINER : NONE
        "url" : _url,
        "product_id" : _product_id,
        "site_id" : _site_id,
        "status" : _status,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "features" : _features,
        "feature_count" : _feature_count,
        "description" : _description,
        "long_description" : _long_description,
        "click_and_collect" : _click_and_collect,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count" : _image_count,
        "image_urls" : _image_urls,
        "htags" : _htags,
        "keywords" : _keywords,

        # CONTAINER : REVIEWS
        "review_count" : _review_count,
        "average_review" : _average_review,
        "max_review" : _max_review,
        "min_review" : _min_review,
        "reviews" : _reviews,

        # CONTAINER : SELLERS
        "price" : _price,
        "price_amount" : _price_amount,
        "price_currency" : _price_currency,
        "site_online_in_stock" : _site_online_in_stock,
        "site_online": _site_online,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "category_name" : _category_name,
        "brand" : _brand,
        }