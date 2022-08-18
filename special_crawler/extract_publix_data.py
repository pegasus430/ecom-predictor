#!/usr/bin/python

import re
from lxml import html
import urlparse
import requests
import traceback
from product_ranking.guess_brand import guess_brand_from_first_words
from extract_data import Scraper

class PublixScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.publix.com/pd/.*"

    def _extract_page_tree(self):
        try:
            contents = requests.get(self.product_page_url, cookies={'PublixStore': '1083|Publix+At+University+Town+Center'}, timeout=10).text
            self.page_raw_text = contents
            self.tree_html = html.fromstring(contents)
        except Exception as e:
            print traceback.format_exc(e)

    def check_url_format(self):
        m = re.match(r"^https?://www.publix.com/pd/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        is_product = self.tree_html.xpath('//div[contains(@class, "product-page")]')
        return False if is_product else True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _product_id(self):
        product_id = self.tree_html.xpath('//button[contains(@id, "ProductAddToCart")]/@productid')
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath('//span[contains(@id, "ProductSummary_productTitleLabel")]/text()')
        return product_name[0] if product_name else None

    def _title_seo(self):
        return self._product_name()

    def _brand(self):
        brand = re.search(r'brand\":\ \"(.*?)\"', self.page_raw_text)
        if brand:
            return brand.group(1)
        else:
            return guess_brand_from_first_words(self._product_name())

    def _product_title(self):
        return self._product_name()

    def _description(self):
        url = self.tree_html.xpath('//a[@id="link_tab_overview"]/@href')
        if not url:
            return None
        url = urlparse.urljoin(self.product_page_url, url[0])
        try:
            content = requests.get(url, timeout=10).text
            content = html.fromstring('<div>' + content + '</div>')
            long_desc = content.xpath('//*[contains(@id, "OverviewRepeater_OverviewText")]/text()')
            return long_desc[0] if long_desc else None
        except:
            return None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _image_urls(self):
        images = self.tree_html.xpath('//div[@id="ProductImages"]'
                                      '//div[@class="thumbnails"]'
                                      '//img[contains(@class, "productImage-s")]'
                                      '/@data-largimage')
        image_list = []
        for image in images:
            image_list.append('http:' + image)
        return image_list if images else None

    def _categories(self):
        categories = self.tree_html.xpath('//ul[@class="breadcrumb"]//li//a')
        category_list = []
        if categories:
            for category in categories[1:-1]:
                text = self._clean_text(html.tostring(category))
                category_list.append(self._find_between(text, '>', '<span'))
            return category_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.tree_html.xpath('//input[@id="finalPrice"]/@value')
        return float(price[0]) if price else None

    def _price_currency(self):
        return "USD"

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        in_stock = self.tree_html.xpath('//span[@class="available-in"]/text()')
        return 0 if in_stock else 1

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id": _product_id, \
 \
        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name, \
        "product_title": _product_title, \
        "title_seo": _title_seo,
        "description" : _description, \
 \
        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls, \
        "categories": _categories, \
 \
        # CONTAINER : SELLERS
        "price_amount": _price_amount, \
        "price_currency": _price_currency, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "brand": _brand, \
        }