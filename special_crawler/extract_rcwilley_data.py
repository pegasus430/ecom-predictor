#!/usr/bin/python

import re
import urlparse

from extract_data import Scraper


class RcwilleyScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.rcwilley.com/<category-name>"

    REVIEW_URL = "https://rcwilley.ugc.bazaarvoice.com/0593-en_us/{0}/reviews.djs?format=embeddedhtml"

    def check_url_format(self):
        m = re.match(r"^https?://www.rcwilley.com/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')

        if itemtype and itemtype[0] == "product":
            return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath("//span[@itemprop='sku']/text()")
        if product_id:
            product_id = re.search('\d+', product_id[0])
        return product_id.group() if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[@itemprop='name']//strong/text()")
        return self._clean_text(product_name[0]) if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _model(self):
        return self._product_id()

    def _description(self):
        description = self.tree_html.xpath("//div[@itemprop='description']//h2/text()")
        return ''.join(description) if description else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_url_list = []
        image_urls_info = self.tree_html.xpath("//div[@id='additionalImages']//img/@data-src")
        if image_urls_info:
            image_urls = image_urls_info
        else:
            image_urls = self.tree_html.xpath("//img[@id='mainImage']/@src")
        if image_urls:
            for image_url in image_urls:
                image_url_list.append(urlparse.urljoin(self.product_page_url, image_url))

        return image_url_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.tree_html.xpath("//meta[@itemprop='price']/@content")
        return float(price[0]) if price else None

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//ul[@id='breadCrumbs']//span[@itemprop='title']/text()")
        return categories if categories else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

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
        "product_title": _product_title,
        "title_seo": _title_seo,
        "model": _model,
        "description": _description,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        }
