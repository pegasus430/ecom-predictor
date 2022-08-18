#!/usr/bin/python

import re
import urlparse

from lxml import html
from product_ranking.guess_brand import guess_brand_from_first_words
from extract_data import Scraper


class SuperdrugScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.superdrug.com/<category-name>/<product-name>"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
            "passkey=i5l22ijc8h1i27z39g9iltwo3" \
            "&apiversion=5.5" \
            "&displaycode=10798-en_gb" \
            "&resource.q0=products" \
            "&filter.q0=id:eq:{}" \
            "&stats.q0=reviews"

    def check_url_format(self):
        m = re.match(r"^https?://www.superdrug.com/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath("//input[@name='productID']/@value")
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//meta[@property='og:title']/@content")

        return product_name[0] if product_name else None

    def _description(self):
        short_description = self.tree_html.xpath("//meta[@name='description']/@content")
        return short_description[0] if short_description else None

    def _long_description(self):
        long_description = []
        description_info = self.tree_html.xpath("//div[contains(@class, 'panel-body--sd-base')]/p")
        for description in description_info:
            long_description.append(html.tostring(description))
        long_description = self._clean_text(''.join(long_description))

        return long_description

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _video_urls(self):
        video_urls = []
        video_urls_info = self.tree_html.xpath("//a[contains(@class, 'productVideoIcon')]/@data-youtube")
        for video_url in video_urls_info:
            video_urls.append('https://www.youtube.com/embed' + video_url)
        return video_urls

    def _image_urls(self):
        images = self.tree_html.xpath("//ul[contains(@id, 'thumbnails')]/li/a/img/@src")

        return [urlparse.urljoin(self.product_page_url, image) for image in images] if images else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price_amount(self):
        price = self.tree_html.xpath("//span[@class='pricing__now']/text()")
        return float(self._clean_text(price[0])) if price else None

    def _price_currency(self):
        return "GBP"

    def _temp_price_cut(self):
        origin_price = self.tree_html.xpath("//span[@class='strikethrough']/text()")
        return 1 if origin_price else 0

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        stock_status = self.tree_html.xpath('//span[@itemprop="availability"]/text()')
        if stock_status and stock_status[0].lower() == 'instock':
            return 0
        return 1

    def _in_stores_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//div[contains(@class, 'breadcrumb')]//a/text()")

        return categories[1:] if categories else None

    def _brand(self):
        brand = None
        if self.review_json:
            if self.review_json.get('Brand', {}):
                brand = self.review_json['Brand']['Name']
        if not brand:
            brand = re.search("'brand': '(.*?)',", html.tostring(self.tree_html))
            brand = brand.group(1) if brand else guess_brand_from_first_words(self._product_name())

        return brand

    def _clean_text(self, text):
        return re.sub("[\r\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "description": _description,
        "long_description": _long_description,

        # CONTAINER : PAGE_ATTRIBUTES
        "video_urls": _video_urls,
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "price_currency": _price_currency,
        "temp_price_cut": _temp_price_cut,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
