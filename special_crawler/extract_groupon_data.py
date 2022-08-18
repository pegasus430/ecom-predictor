# -*- coding: utf-8 -*-
#!/usr/bin/python

import re
import json
import requests
import traceback

from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words


class GrouponScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################
    # https://www.groupon.com/deals/gs-nest-learning-thermostat-3rd-generation
    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.groupon.com/deals/<product-name>"

    SUBSCRIBE_URL = 'https://www.groupon.com/app/subscriptions'

    payload = {"email_address": 'tester@test.com'}

    def _extract_page_tree(self):
        for i in range(3):
            try:
                with requests.Session() as s:
                    s.post(self.SUBSCRIBE_URL, data=json.dumps(self.payload), timeout=5)
                    response = s.get(self.product_page_url)

                    if self.lh:
                        self.lh.add_log('status_code', response.status_code)

                    if response.ok:
                        content = response.text
                        self.tree_html = html.fromstring(content)
                        return

                    else:
                        self.ERROR_RESPONSE['failure_type'] = response.status_code

            except Exception as e:
                print('Error Extracting Page Tree: {}'.format(traceback.format_exc(e)))

        self.is_timeout = True  # return failure

    def check_url_format(self):
        m = re.match(r"^(http|https)://www.groupon.com/.*?$", self.product_page_url)
        return not not m

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')[0].strip()
        if itemtype != "groupon:deal":
            return True

        self.product_json = self._product_json()

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath('//section[@class="module deal"]/@data-bhc')
        if product_id:
            product_id = product_id[0].replace('deal:', '').strip()

        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//div[@class="options-metadata"]//meta[@itemprop="name"]/@content')
        if not product_name:
            product_name = self.tree_html.xpath('//*[@id="deal-title"]/text()')
        return product_name[0].strip() if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        title = self.tree_html.xpath("//meta[@property='og:title']/@content")
        return title[0].strip() if title else self._product_name()

    def _long_description(self):
        long_description = self.tree_html.xpath(
            "//div[@itemprop='description']"
            "//section//ul"
        )
        if long_description:
            long_description = self._clean_text(html.tostring(long_description[0]))

        return long_description

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []
        if not self.product_json:
            return None

        try:
            images_info = self.product_json['carousel']['dealImages']
            for image in images_info:
                image_urls.append(image.get('media'))
        except Exception as e:
            print('Error while parsing Image Urls: {}'.format(traceback.format_exc(e)))

        return image_urls if image_urls else None

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        avg_info = self.tree_html.xpath("//div[@class='product-reviews-average-rating']/text()")
        if avg_info:
            try:
                avg_info = float(avg_info[0])
            except:
                avg_info = None

        return avg_info

    def _review_count(self):
        review_count = self.tree_html.xpath(
            "//article[@id='product-reviews']"
            "//a[@class='product-reviews-anchor']/text()")
        if review_count:
            try:
                review_count = int(re.findall(r'(\d+)', review_count[0].replace(',', ''))[0])
            except:
                review_count = None

        return review_count

    def _reviews(self):
        rating_star_list = self.tree_html.xpath(
            "//div[@id='product-reviews-quick-view-tooltip']"
            "//table//tr")

        if rating_star_list:
            review_list = [[1, 0], [2, 0], [3, 0], [4, 0], [5, 0]]

            for rating in rating_star_list:
                try:
                    rating_star_info = rating.xpath(".//ul[@class='product-reviews-rating']/@data-bhc")
                    rating_star = int(re.findall(r'(\d+)', rating_star_info[0])[0])
                    rating_value_info = rating.xpath("./@data-bhc")
                    rating_value = int(re.search('_(\d+)', rating_value_info[0]).group(1))
                    review_list[rating_star - 1][1] = rating_value
                except Exception as e:
                    print('Error while parsing Reviews: {}'.format(traceback.format_exc(e)))
                    continue

            return review_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//meta[@itemprop='price']/@content")
        if not price:
            price = self.tree_html.xpath("//div[contains(@class, 'breakout-option-price')]/text()")
        return price[0].strip() if price else None

    def _price_amount(self):
        amount = None
        try:
            amount = float(self._price()[1:])
        except Exception as e:
            print('Error while parsing Price: {}'.format(traceback.format_exc(e)))

        return amount

    def _price_currency(self):
        currency = self.tree_html.xpath("//meta[@itemprop='priceCurrency']/@content")
        return currency[0] if currency else None

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//section[@class='breadcrumbs']//a[@class='crumb']/text()")
        return categories[1:] if categories else None

    def _category_name(self):
        categories = self._categories()
        return categories[-1] if categories else None

    def _brand(self):
        return guess_brand_from_first_words(self._product_name())

    def _sku(self):
        sku = self.tree_html.xpath("//meta[@itemprop='sku']/@content")
        return sku[0] if sku else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    def _product_json(self):
        product_info = self._find_between(html.tostring(self.tree_html), 'window.payload =', ';').strip()
        try:
            return json.loads(product_info)
        except:
            return None

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
        "long_description" : _long_description, \
        "sku" : _sku, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count" : _image_count,\
        "image_urls" : _image_urls, \

        # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \
        "reviews" : _reviews, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "price_amount" : _price_amount, \
        "price_currency" : _price_currency, \
        "site_online" : _site_online, \
        "site_online_out_of_stock" : _site_online_out_of_stock, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "category_name" : _category_name, \
        "brand" : _brand, \

        }
