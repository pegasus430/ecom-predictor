#!/usr/bin/python

import re
from product_ranking.guess_brand import guess_brand_from_first_words
from extract_data import Scraper


class PriceLineScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.priceline.com.au/.*"

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^https?://www.priceline.com.au/.*$", self.product_page_url)
        return not not m

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """
        if len(self.tree_html.xpath('//div[@itemtype="http://schema.org/Product"]')) < 1:
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
        product_name = self.tree_html.xpath('//div[@class="product-name"]'
                                            '//span[@itemprop="name"]/text()')
        if product_name:
            return product_name[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _sku(self):
        sku = self.tree_html.xpath('//span[@itemprop="sku"]/text()')
        if sku:
            return sku[0]

    def _description(self):
        short_description = self.tree_html.xpath('//div[contains(@class, "product-main-info")]'
                                                 '/div[@itemprop="description"]/text()')
        if short_description:
            return short_description[0].strip()

    def _brand(self):
        brand = self.tree_html.xpath('//span[@itemprop="brand"]/text()')
        if brand:
            return brand[0]
        return guess_brand_from_first_words(self._product_name())

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//div[contains(@class, "product-image")]'
                                          '/a/img[@itemprop="image"]/@src')
        if image_urls:
            return image_urls

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath('//span[@itemprop="price"]/text()')
        if price:
            return price[0]

    def _price_amount(self):
        price = self._price()
        return float(price.replace('$', '').replace(',', ''))

    def _price_currency(self):
        return 'AUD'

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        in_stock = None
        stock_info = self.tree_html.xpath('//meta[@property="product:availability"]/@content')

        if stock_info:
            in_stock = stock_info[0].lower()
        if in_stock == 'in stock':
            return 0
        return 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        category_list = []
        category_temp = self.product_page_url.split('https://www.priceline.com.au/')[1]
        categories = category_temp.split('/')[:-1]
        for category in categories:
            category = category.replace('-', ' ').replace('and', '&')
            category_list.append(category)
        return category_list

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
        "sku": _sku, \
        "description": _description, \
        "brand": _brand, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count": _image_count,\
        "image_urls": _image_urls, \

        # CONTAINER : SELLERS
        "price": _price, \
        "price_amount": _price_amount, \
        "price_currency": _price_currency, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \

        # CONTAINER : CLASSIFICATION
        "categories": _categories, \
        "category_name": _category_name, \
        }
