# -*- coding: utf-8 -*-
#!/usr/bin/python

import re

from lxml import html
from extract_data import Scraper


class AuchanfrScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.auchan.fr/.*"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
                         "passkey=syzh21yn6lf39vjo00ndkig63&apiversion=5.5&" \
                         "displaycode=6073-fr_fr&" \
                         "resource.q0=products&" \
                         "filter.q0=id:eq:{}&" \
                         "stats.q0=reviews"

    def check_url_format(self):
        m = re.match(r"^https?://www.auchan.fr/.*$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[@itemtype="http://schema.org/Product"]')) < 1:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = re.findall('config.productCode = (.*?);', html.tostring(self.tree_html))
        if product_id:
            return product_id[0].replace('"', '')

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[contains(@class,'product-detail--title')]//font/text()")
        if product_name:
            return product_name[0].strip()

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _features(self):
        lis = self.tree_html.xpath("//div[contains(@class, 'tab-technical-description')]//ul/li")
        features_list = []
        for li in lis:
            feature = li.xpath(".//text()")
            feature = [r.strip() for r in feature if len(r.strip())>0]
            feature = ' '.join(feature)
            features_list.append(feature)
        if features_list:
            return features_list

    def _description(self):
        short_description = self.tree_html.xpath('//section[@id="tabDescription"]'
                                                 '/main//p/text()')
        if short_description:
            return short_description[0].strip()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):        
        image_list = self.tree_html.xpath('//div[@class="product-thumbnail--container"]'
                                          '//label/img/@src')

        if image_list:
            return image_list
        elif self.tree_html.xpath("//meta[@itemprop='image']/@content"):
            main_image_url = self.tree_html.xpath("//meta[@itemprop='image']/@content")

            return main_image_url

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath('//meta[@itemprop="price"]/@content')
        if price:
            return '€{:2,.2f}'.format(round(float(price[0]), 2))

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        return self.tree_html.xpath("//div[contains(@class, 'breadcrumb')]"
                                    "//a[@itemprop='item']//text()")

    def _brand(self):
        return self.tree_html.xpath('//meta[@itemprop="brand"]/@content')[0]

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id": _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name, \
        "product_title": _product_title, \
        "title_seo": _title_seo, \
        "features": _features, \
        "description": _description, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls, \

        # CONTAINER : SELLERS
        "price": _price, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \

        # CONTAINER : CLASSIFICATION
        "categories": _categories, \
        "brand": _brand, \
        }
