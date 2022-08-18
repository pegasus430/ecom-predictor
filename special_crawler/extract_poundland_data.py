# -*- coding: utf-8 -*-
#!/usr/bin/python

import re
import requests
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words
from lxml import html


class PoundLandScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.poundland.co.uk/.*"
    REVIEW_URL = "http://www.poundland.co.uk/ajax-rating/add/?product_id={product_id}"

    def __init__(self, **kwargs):  # **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.review_count = None
        self.reviews = None
        self.average_review = None
        self.reviews_checked = False

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^https?://www.poundland.co.uk/.*$", self.product_page_url)
        return not not m

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """
        if len(self.tree_html.xpath('//div[contains(@class, "product-view")]')) < 1:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath('//input[@name="product"]/@value')
        if product_id:
            return product_id[0]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath('//div[contains(@class, "product-name")]'
                                            '/h1/text()')
        if product_name:
            return product_name[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        short_description = self.tree_html.xpath('//meta[@name="description"]/@content')
        if short_description:
            return short_description[0]

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_list = []
        image_urls = self.tree_html.xpath('//div[contains(@class, "product-image")]'
                                          '/img/@src')
        if image_urls:
            image_list.append(image_urls[-1])
            return image_list

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    def _brand(self):
        brand = self.tree_html.xpath('//div[contains(@class, "product-brand")]'
                                     '/img/@alt')
        if brand:
            return brand[0]

        return guess_brand_from_first_words(self._product_name())

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################
    def _reviews(self):
        if self.reviews_checked:
            return self.reviews

        self.reviews_checked = True

        url = self.REVIEW_URL.format(product_id=self._product_id())
        data = requests.get(url=url, timeout=10).json()

        self.review_count = int(data['rating_count'])
        percent_review = float(data['rating_percentage'])
        self.average_review = round(float(str(percent_review / 100 * 5)), 1)

        return None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath('//div[contains(@class, "product-image")]'
                                     '/img/@alt')
        if price:
            price = re.search('\xa3(.*)', price[0])
            return price.group() if price else None

    def _price_amount(self):
        price = self._price()
        price = re.search('\d+\.?\d+', price).group()
        return float(price)

    def _price_currency(self):
        return 'GBP'

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        category_list = []

        category_ajax = requests.get("http://www.poundland.co.uk/ajax-breadcrumbs/ajax/").json()

        category_ids = re.search('product_category_ids: {(.*)}', html.tostring(self.tree_html))
        if category_ids:
            category_ids = category_ids.group(1).split(',')

        category_ajax_id = category_ids[0].split(':')[0].replace('"', '')
        if category_ajax_id in category_ajax:
            category_list.append(category_ajax[category_ajax_id]['name'])

            if category_ajax[category_ajax_id]['parent_id']:
                category_parent_id = category_ajax[category_ajax_id]['parent_id']
                category_list.append(category_ajax[str(category_parent_id)]['name'])

                if category_ajax[str(category_parent_id)]['parent_id']:
                    category_sub_parent_id = category_ajax[str(category_parent_id)]['parent_id']
                    category_list.append(category_ajax[str(category_sub_parent_id)]['name'])

                    if category_ajax[str(category_sub_parent_id)]['parent_id']:
                        category_main_parent_id = category_ajax[str(category_sub_parent_id)]['parent_id']
                        category_list.append(category_ajax[str(category_main_parent_id)]['name'])

        return list(reversed(category_list))

    def _category_name(self):
        return self._categories()[-1]

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id": _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo": _title_seo, \
        "description": _description, \
        "brand": _brand, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count": _image_count,\
        "image_urls": _image_urls, \

        # CONTAINER : REVIEWS
        "reviews": _reviews, \

        # CONTAINER : SELLERS
        "price": _price, \
        "price_amount": _price_amount, \
        "price_currency": _price_currency, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "marketplace": _marketplace, \

        # CONTAINER : CLASSIFICATION
        "categories": _categories, \
        "category_name": _category_name, \
        }
