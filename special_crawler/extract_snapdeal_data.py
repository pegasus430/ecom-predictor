#!/usr/bin/python

import re
from lxml import html
import requests

from extract_data import Scraper
from spiders_shared_code.snapdeal_variants import SnapdealVariants


class SnapdealScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    REVIEW_URL = 'https://www.snapdeal.com/review/stats/{product_id}'

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.snapdeal.com/product/<product-name>/<product-id>"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.sv = SnapdealVariants()

    def check_url_format(self):
        m = re.match("https?://www\.snapdeal\.com/product/.*", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if self.tree_html.xpath("//meta[@property='og:type']/@content")[0] != "snapdeallog:item":
            return True

        self.sv.setupCH(self.tree_html)

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.product_page_url.split('/')[-1]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.tree_html.xpath("//meta[@name='og_title']/@content")[0].strip()

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _features(self):
        features = []

        features_td_list = self.tree_html.xpath("//table[@class='product-spec']//tr/td")

        for index, td in enumerate(features_td_list):
            if (index + 1) % 2 != 0:
                continue

            features.append(features_td_list[index - 1].text_content() + " " + td.text_content())

        if features:
            return features

    def _description(self):
        short_description = None

        spec_title_list = self.tree_html.xpath("//h3[@class='spec-title']")

        for spec_title in spec_title_list:
            if "Highlights" in spec_title.text_content():
                short_description = spec_title.xpath("./../following-sibling::div[@class='spec-body']")[0].text_content().strip()
                break

        if short_description:
            return short_description

    def _long_description(self):
        long_description = self.tree_html.xpath("//div[@itemprop='description' and @class='detailssubbox']")

        if long_description:
            return long_description[0].text_content().strip()

    def _variants(self):
        return self.sv._variants()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
 
    def _image_urls(self):
        image_urls = self.tree_html.xpath("//div[@class='baseSliderPager']//img/@src")
        lazy_image_urls = self.tree_html.xpath("//div[@class='baseSliderPager']//img/@lazysrc")
        image_urls = image_urls + lazy_image_urls

        if not image_urls:
            image_urls = self.tree_html.xpath("//div[@id='bx-pager-left-image-panel']//img/@src")
            lazy_image_urls = self.tree_html.xpath("//div[@id='bx-pager-left-image-panel']//img/@lazysrc")
            image_urls = image_urls + lazy_image_urls

        if image_urls:
            return image_urls

    def _video_urls(self):
        iframe_list = self.tree_html.xpath("//iframe")

        youtubu_iframes = []

        for iframe in iframe_list:
            if "www.youtube.com" in iframe.xpath("./@lazysrc")[0]:
                youtubu_iframes.append(iframe)

        youtubu_urls = []

        for iframe in youtubu_iframes:
            youtubu_urls.append(iframe.xpath("./@lazysrc")[0].strip())

        if youtubu_urls:
            return youtubu_urls

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        if self.is_review_checked:
            return self.reviews

        self.is_review_checked = True

        product_id = self._product_id()

        review_content = requests.get(self.REVIEW_URL.format(product_id=product_id), timeout=10).text
        review_content = html.fromstring(review_content)
        rating_blocks = review_content.xpath("//div[@class='product_infogram']//div[contains(@class, 'row')]")

        review_list = []
        max_review = None
        min_review = None

        for rating_block in rating_blocks:
            review_rate = int(rating_block.xpath(".//span[contains(@class, 'lfloat')]/text()")[0][0])
            review_count = int(rating_block.xpath(".//span[contains(@class, 'barover')]/following-sibling::span/text()")[0])
            review_list.append([review_rate, review_count])

            if not max_review:
                max_review = review_rate
            elif review_count > 0 and review_rate > max_review:
                max_review = review_rate

            if not min_review:
                min_review = review_rate
            elif review_count > 0 and review_rate < min_review:
                min_review = review_rate

        self.reviews = review_list
        self.average_review = float(self.tree_html.xpath("//span[@itemprop='ratingValue']/text()")[0].strip())
        self.review_count = int(self.tree_html.xpath("//span[@itemprop='ratingCount']/text()")[0].strip())
        self.max_review = max_review
        self.min_review = min_review

        return self.reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        return '{} {}'.format(self._price_currency(),  self.tree_html.xpath("//span[@itemprop='price']/text()")[0])

    def _price_amount(self):
        price_amount = self.tree_html.xpath("//input[@id='productPrice']/@value")[0]

        if str(int(price_amount)) == price_amount:
            return int(price_amount)
        else:
            return float(price_amount)

    def _price_currency(self):
        return 'Rs.'

    def _site_online(self):
        return 1

    def _in_stores(self):
        return 1

    def _site_online_out_of_stock(self):
        if self.tree_html.xpath("//div[@class='container-fluid inStockNotify reset-padding ']"):
            return 1

        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################    

    def _categories(self):
        return self.tree_html.xpath("//div[@class='containerBreadcrumb']//span[@itemprop='title']/text()")

    def _brand(self):
        return self.tree_html.xpath("//input[@id='brandName']/@value")[0]

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
        "features" : _features, \
        "description" : _description, \
        "long_description" : _long_description, \
        "variants": _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls, \
        "video_urls" : _video_urls, \

        # CONTAINER : REVIEWS
        "reviews" : _reviews, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "price_amount" : _price_amount, \
        "price_currency" : _price_currency, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "in_stores" : _in_stores, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "brand" : _brand, \
        }
