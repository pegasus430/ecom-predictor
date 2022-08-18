# -*- coding: utf-8 -*-
#!/usr/bin/python

import re
import json
import requests
import traceback

from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words
from spiders_shared_code.barnesandnoble_variants import BarnesandnobleVariants


class BarnesandnobleScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################
    # http://www.barnesandnoble.com/w/toys-games-pop-animation-peanuts-peppermint-patty/30447396
    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.barnesandnoble.com/w/<product-name>/<stream-id>"

    REVIEW_URL = 'https://comments.us1.gigya.com/comments.getComments?categoryID=Products&streamID={stream_id}&includeStreamInfo=true&APIKey={api_key}&start={start}'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.bvt = BarnesandnobleVariants()
        self.variants = None
        self.is_variant_checked = False

        self.review_info = []
        self.reviews = []
        self.stream_info = None

    def check_url_format(self):
        m = re.match(r"^https?://www.barnesandnoble.com/.*?$", self.product_page_url)
        return not not m

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')[0].strip()

        if itemtype != "product":
            return True

        self.product_json = self._product_json()
        self._get_stream_info()
        self._get_review_info()

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        if self.product_json:
            try:
                product_id = self.product_json['product'][0]['productInfo']['productID'].replace('prd', '')
                return product_id
            except:
                pass

        product_id = self.tree_html.xpath("//input[contains(@name, 'productId')]/@value")
        if product_id:
            product_id = product_id[0].replace('prd', '')

        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        if self.product_json:
            try:
                product_name = self.product_json['product'][0]['productInfo']['productName']
                return product_name
            except:
                pass

        product_name = self.tree_html.xpath("//h1[@itemprop='name']/text()")

        return product_name[0] if product_name else None

    def _product_title(self):
        return self.tree_html.xpath('//meta[@property="og:title"]/@content')[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath('//meta[@property="og:title"]/@content')[0].strip()

    def _description(self):
        description = self.tree_html.xpath("//div[@id='productInfoOverview']//*[not(self::h2)]//text()")
        description = ' '.join(description)

        return self._clean_text(description)

    def _variants(self):
        if self.is_variant_checked:
            return self.variants

        self.is_variant_checked = True

        self.bvt.setupCH(self.tree_html)
        self.variants = self.bvt._variants()

        return self.variants

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []
        image_list = []

        main_image = self.tree_html.xpath("//img[@id='pdpMainImage']/@src")
        thumb_images = self.tree_html.xpath("//div[contains(@class, 'product-thumb')]/a/img/@src")

        if thumb_images:
            image_urls.extend(thumb_images)
        elif main_image:
            image_urls.append(main_image[0])
        else:
            return None

        for image in image_urls:
            try:
                size_info = re.search('_s(.+?).jpg', image).group(1)
                image_list.append('http:' + image.replace(size_info, '1200x630'))
            except:
                continue

        return image_list if image_list else None

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        try:
            avg_review = self.stream_info['streamInfo']['avgRatings']['_overall']
        except:
            avg_review = None

        return avg_review

    def _review_count(self):
        try:
            review_count = self.stream_info['streamInfo']['ratingCount']
        except:
            review_count = 0

        return review_count

    def _reviews(self):
        reviews = []
        review_list = [[1, 0], [2, 0], [3, 0], [4, 0], [5, 0]]
        for comment in self.review_info:
            try:
                reviews.append(comment['ratings']['_overall'])
            except Exception as e:
                print traceback.format_exc(e)

        for review in reviews:
            review_list[review - 1][1] += 1
            self.reviews.extend(review_list)

        return review_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//span[contains(@class, 'current-price')]/text()")
        return '$' + price[0] if price else None

    def _temp_price_cut(self):
        if self.tree_html.xpath('//div[@class="bbNav4Sale"]'):
            return 1
        return 0

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        out_of_stock = None
        if self.product_json:
            try:
                out_of_stock = int(self.product_json['product'][0]['attributes']['outOfStock'])
            except:
                pass

        return out_of_stock

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        return guess_brand_from_first_words(self._product_name())

    def _category_name(self):
        category_name = None
        if self.product_json:
            try:
                category_name = str(self.product_json['product'][0]['category']['primaryCategory'])
            except:
                pass

        return category_name

    def _sku(self):
        try:
            sku = self.product_json['product'][0]['productInfo']['sku']
            return sku
        except:
            return None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    def _product_json(self):
        product_info = self._find_between(html.tostring(self.tree_html), 'digitalData =', ';').strip()
        try:
            return json.loads(product_info)
        except:
            return None

    def _get_api_key(self):
        return self._find_between(html.tostring(self.tree_html), 'apiKey=', '"').strip()

    def _get_stream_id(self):
        stream_id = self.tree_html.xpath("//a[@id='writeReviewBtn']/@data-work-id")
        return stream_id[0] if stream_id else None

    def _get_stream_info(self):
        api_key = self._get_api_key()
        stream_id = self._get_stream_id()

        if api_key and stream_id:
            review_url = self.REVIEW_URL.format(stream_id=stream_id, api_key=api_key, start=0)
            try:
                self.stream_info = requests.get(review_url).json()
            except:
                self.stream_info = None

        return self.stream_info

    def _get_review_info(self):
        api_key = self._get_api_key()
        stream_id = self._get_stream_id()

        if api_key and stream_id:
            total_count = self._review_count()
            start = 0

            while start <= total_count:
                review_url = self.REVIEW_URL.format(stream_id=stream_id, api_key=api_key, start=start)
                try:
                    stream_info = requests.get(review_url, timeout=5).json()
                    review_info = stream_info.get('comments')
                    # prevent infinite loop
                    if not review_info:
                        break
                    self.review_info.extend(review_info)
                    start = len(self.review_info)
                except:
                    break

        return self.review_info

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id" : _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "description" : _description, \
        "variants" : _variants, \
        "sku" : _sku, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls, \

        # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \
        "reviews" : _reviews, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "temp_price_cut": _temp_price_cut, \
        "in_stores" : _in_stores, \
        "site_online" : _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \

        # CONTAINER : CLASSIFICATION
        "brand": _brand,
        "category_name" : _category_name, \
        }
