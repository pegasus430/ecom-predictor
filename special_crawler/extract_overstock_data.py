#!/usr/bin/python

import re
import json
import traceback

from lxml import html
from extract_data import Scraper

from product_ranking.guess_brand import guess_brand_from_first_words

class OverstockScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries(use_session = True, max_retries=10)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')

        if itemtype and itemtype[0].strip() == "product":
            return False
 
        return True

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//div[@itemprop='name']//h1/text()")
        if not product_name:
            product_name = self.tree_html.xpath("//div[@class='product-title']//h1/text()")
        return product_name[0].strip() if product_name else None

    def _model(self):
        model = self.tree_html.xpath("//td[@itemprop='mpn']/text()")
        return ''.join(model) if model else None

    def _description(self):
        short_description = self.tree_html.xpath("//span[@itemprop='description']//text()")
        return self._clean_text(short_description[0]) if short_description else None

    def _long_description(self):
        long_description = self.tree_html.xpath("//span[@itemprop='description']//ul")
        if long_description:
            long_description = self._clean_text(html.tostring(long_description[0]))
        return long_description

    def _no_longer_available(self):
        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath(
            "//div[contains(@class, 'image-gallery gallery-container')]"
            "//div[contains(@class, 'thumb-frame')]"
            "//ul//li//@data-max-img")
        return image_urls if image_urls else None

    def _video_urls(self):
        video_urls = re.search('videoUrl : (.*?),', html.tostring(self.tree_html), re.DOTALL)
        if video_urls:
            video_urls = video_urls.group(1).strip().replace('"', '')
        return video_urls

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        average_review = re.search(r'reviewAverage:\s\"(\d+(?:\.\d+)?)\"', self.page_raw_text)
        if average_review:
            return float(average_review.group(1))

    def _review_count(self):
        review_count = re.search(r'reviewCount:\s(\d+),', self.page_raw_text)
        if review_count:
            return review_count.group(1)

    def _reviews(self):
        rating_by_stars = [[5, 0], [4, 0], [3, 0], [2, 0], [1, 0]]
        for i in reversed(range(5)):
            value = re.search(r"count%i:\s\'(\d+)\'" % (i + 1), self.page_raw_text)
            if value:
                rating_by_stars[4 - i][1] = int(value.group(1))

        return rating_by_stars if sum([x[1] for x in rating_by_stars]) != 0 else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.tree_html.xpath('//*[@itemprop="price"]/@content')
        return float(price[0]) if price else None

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        stock_status = self.tree_html.xpath('//div[@class="product-labels"]//div/text()')
        if stock_status and stock_status[0].lower() == 'out of stock':
            return 1
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath(
            "//ul[@class='breadcrumbs']"
            "//span[@itemprop='title']/text()")
        if not categories:
            categories = self.tree_html.xpath("//ul[@class='breadcrumbs']//li//a//span/text()")

        return [c.strip() for c in categories] if categories else None
    
    def _brand(self):
        return guess_brand_from_first_words(self._product_name())

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "model" : _model,
        "description" : _description,
        "long_description" : _long_description,
        "no_longer_available" : _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "video_urls" : _video_urls,

        # CONTAINER : REVIEWS
        "reviews" : _reviews,
        "average_review" : _average_review,
        "review_count" : _review_count,

        # CONTAINER : SELLERS
        "price_amount" : _price_amount,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
