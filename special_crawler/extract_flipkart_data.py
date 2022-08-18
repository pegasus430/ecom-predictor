#!/usr/bin/python

import re
import json
import traceback

from lxml import html
from extract_data import Scraper
from spiders_shared_code.flipkart_variants import FlipkartVariants


class FlipkartScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.flipkart.com/<product-name>/p/<product-id>"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        # whether product has any webcollage media
        self.reviews = None
        self.product_json = None

    def check_url_format(self):

        m = re.match(r"^https?://www\.flipkart\.com/.*/p/.*$", self.product_page_url)

        return bool(m)

    def not_a_product(self):
        self._extract_product_json()
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_product_json(self):
        try:
            self.product_json = json.loads(self.tree_html.xpath('//script[@type="application/ld+json"]')[0].text_content(),
                                           strict=False)
        except:
            print traceback.format_exc()

    def _product_id(self):
        productId_info = re.search('"productId":(.*?)}', html.tostring(self.tree_html))
        return productId_info.group(1).replace('\"', '') if productId_info else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return ''.join(self.tree_html.xpath("//h1[@class='_3eAQiD']/text()"))

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _model(self):
        return self._product_id()

    def _description(self):
        description = None
        first_description = self.tree_html.xpath("//div[@class='bzeytq _3cTEY2']/text()")

        if first_description:
            description = self._clean_text(first_description[0])
        if not description:
            p_description = self.tree_html.xpath("//div[@class='bzeytq _3cTEY2']//p/text()")
            if p_description:
                description = self._clean_text(p_description[0])

        return description

    def _long_description(self):
        long_description = []
        long_description_title = self.tree_html.xpath("//div[@class='_1GuuTl']/text()")
        long_description_content = self.tree_html.xpath("//div[@class='DQKXPi']//p/text()")

        try:
            for i, attribute in enumerate(long_description_title):
                long_description.append(long_description_title[i] + ': ' + long_description_content[i])
        except:
            pass

        return ', '.join(long_description) if long_description else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
        
    def _image_urls(self):
        image_list = []
        main_image = self.tree_html.xpath("//div[@class='_2SIJjY']//img/@src")
        urls = self.tree_html.xpath("//div[@class='_1kJJoT']/@style")
        for url in urls:
            image_list.append(self._find_between(url, 'url(', ');').replace('128/', '832/'))
        if not image_list and main_image:
            image_list.append(main_image[0])
        return image_list

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _features(self):
        return self.tree_html.xpath("//li[@class='_2-riNZ']/text()")

    def _average_review(self):
        average_rating = self.tree_html.xpath("//div[@class='_1i0wk8']/text()")
        return float(average_rating[0]) if average_rating else None

    def _review_count(self):
        reviews = self._reviews()

        if not reviews:
            return 0

        review_count = 0

        for review in reviews:
            review_count = review_count + review[1]

        return review_count

    def _reviews(self):
        rating_list = self.tree_html.xpath('//div[@class="CamDho"]/text()')
        reviews = []
        for i in range(0, 5):
            if rating_list:
                reviews.append([5 - i, int(rating_list[i].replace(',', ''))])
            else:
                reviews.append([5 - i, 0])

        return reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        return ''.join(self.tree_html.xpath("//div[@class='_1vC4OE _37U4_g']/text()"))

    def _price_amount(self):
        price_amount = self.tree_html.xpath("//div[@class='_1vC4OE _37U4_g']/text()")
        return float(price_amount[1].replace(',', '')) if len(price_amount) > 1 else None

    def _price_currency(self):
        return "INR"

    def _site_online(self):
        return 1

    def _in_stores(self):
        return 0

    def _site_online_out_of_stock(self):
        is_out_of_stock = self.tree_html.xpath("//div[@class='_3xgqrA']/text()")
        if is_out_of_stock:
            if 'sold out' in is_out_of_stock[0].lower():
                return 1
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//div[@class='_1HEvv0']//a/text()")
        return categories[1:] if categories else None

    def _brand(self):
        return self.product_json[0]['brand']['name'] if self.product_json else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    def _clean_text(self, text):
        return re.sub("[\n\t]", "", text).strip()

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
        "model" : _model, \
        "features" : _features, \
        "description" : _description, \
        "long_description" : _long_description, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls, \

        # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \
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
