#!/usr/bin/python
# -*- coding: utf-8 -*-

import re

from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words
from lxml import html
from HTMLParser import HTMLParser


class AcehardwareScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.acehardware.com/.*"

    def __init__(self, **kwargs):  # **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.reviews_checked = False

    def check_url_format(self):
        m = re.match(r"^https?://www.acehardware.com/.*$", self.product_page_url)
        return not not m

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[contains(@class, "prodMainImage")]')) < 1:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = re.search("productId=(\d+)", html.tostring(self.tree_html)).group(1)
        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath('//div[contains(@id, "prodRCol")]'
                                            '/div/h2[contains(@class, "prodC1")]/text()')
        if product_name:
            return HTMLParser().unescape(product_name[0])

    def _description(self):
        short_description = self.tree_html.xpath('//div[contains(@class, "descriptionContent")]'
                                                 '/div/ul/li/text()')
        return "".join(short_description)

    def _item_num(self):
        item_num = re.search('prodItemNo="(\d+)"', html.tostring(self.tree_html), re.DOTALL)
        if item_num:
            return item_num.group(1)

    def _brand(self):
        brand = self.tree_html.xpath('//span[@class="pr-brand-name"]/text()')
        brand = re.search('(\D+)', brand[0], re.DOTALL)
        if brand:
            brand = brand.group(1).strip()
        else:
            brand = guess_brand_from_first_words(self._product_name())
        return brand

    def _upc(self):
        upc = re.search('upcNo=(\d+)', html.tostring(self.tree_html))
        return upc.group(1) if upc else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath("//ul[@class='product-views']//li//img/@src")
        if not image_urls:
            image_urls = self.tree_html.xpath('//div[contains(@class, "mainImageSize")]'
                                              '//img[@id="mainProdImage"]/@src')
        return image_urls

    def _video_urls(self):
        video_urls = self.tree_html.xpath("//div[@class='videoWrapper']//a/@name")
        return video_urls

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        if self.reviews_checked:
            return self.reviews

        self.reviews_checked = True

        review_count = self.tree_html.xpath('//p[@class="pr-snapshot-average-based-on-text"]'
                                            '/span[@class="count"]/text()')
        self.review_count = int(review_count[0]) if review_count else 0

        average_review = self.tree_html.xpath('//div[contains(@class, "pr-snapshot-rating")]'
                                              '/span[contains(@class, "average")]/text()')
        self.average_review = round(float(str(average_review[0])), 1) if average_review else None

        rating_stars = self.tree_html.xpath('//div[contains(@class, "pr-review-wrap")]'
                                            '//div[@class="pr-review-rating"]/span[contains(@class, "pr-rating")]'
                                            '/text()')
        if rating_stars:
            self.max_review = float(max(rating_stars))
            self.min_review = float(min(rating_stars))

        one_by_star = []
        two_by_star = []
        three_by_star = []
        four_by_star = []
        five_by_star = []

        for rating in rating_stars:
            if rating == '1.0':
                one_by_star.append(rating)
            if rating == '2.0':
                two_by_star.append(rating)
            if rating == '3.0':
                three_by_star.append(rating)
            if rating == '4.0':
                four_by_star.append(rating)
            if rating == '5.0':
                five_by_star.append(rating)

        rating_mark_list = {'1': len(one_by_star), '2': len(two_by_star),
                            '3': len(three_by_star), '4': len(four_by_star),
                            '5': len(five_by_star)}

        self.reviews = rating_mark_list

        return self.reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath('//div[@class="productPrice"]/span/text()')
        if price:
            return price[0]

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        stock = self.tree_html.xpath('//div[@id="quantAddToCart"]/button[@class="disable-add-to-cart"]')
        if stock:
            return 1
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        category_list = []
        categories = self.tree_html.xpath('//div[contains(@id, "crumbs")]//text()')
        for category in categories:
            if category.strip() and not category.strip() == '>':
                category_list.append(category.strip())

        return category_list

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "description": _description,
        "item_num": _item_num,
        "brand": _brand,
        "upc": _upc,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : REVIEWS
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories
    }
