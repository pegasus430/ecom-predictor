#!/usr/bin/python

import urllib
import re
import sys
import json
import os.path
import urllib, cStringIO
from io import BytesIO
from PIL import Image
import mmh3 as MurmurHash
from lxml import html
from lxml import etree
import time
import requests
from extract_data import Scraper


class ChicagoScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://chicago.doortodoororganics.com/shop/products/([a-zA-Z0-9\-_]+)"

    def check_url_format(self):
        #for ex: http://chicago.doortodoororganics.com/shop/products/rudis-white-hamburger-buns
        m = re.match(r"^http://chicago\.doortodoororganics\.com/shop/products/([a-zA-Z0-9\-_]+)$", self.product_page_url)
        return not not m

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _url(self):
        return self.product_page_url

    def _product_id(self):
        script = self.tree_html.xpath("//script//text()")
        script = " ".join(script)
        m = re.findall(r"dtdoRecurringItem.addToSubscription\(([0-9\.]+),", script)
        product_id = m[0]
        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self._clean_text(self.tree_html.xpath("//h1[@itemprop='name']//text()")[0])

    def _product_title(self):
        return self._clean_text(self.tree_html.xpath("//h1[@itemprop='name']//text()")[0])

    def _title_seo(self):
        return self.tree_html.xpath("//title//text()")[0].strip()
    
    def _model(self):
        return None

    def _upc(self):
        return self.tree_html.xpath("//span[@itemprop='sku']//text()")[0].strip()

    def _features(self):
        rows = self.tree_html.xpath("//div[@class='attributes-row']//span//text()")
        # return dict with all features info
        return rows

    def _feature_count(self):
        rows = self.tree_html.xpath("//div[@class='attributes-row']//span//text()")
        return len(rows)

    def _model_meta(self):
        return None

    def _description(self):
        description = "\n".join(self.tree_html.xpath("//p[@itemprop='description']//text()")).strip()
        return description

    def _long_description(self):
        div_tag = self.tree_html.xpath("//div[@class='l-s-prod-left']/div")[1]
        long_description = []
        long_description.append(div_tag.xpath(".//a//text()")[0].strip())

        for span_item in div_tag.xpath(".//span//text()"):
            prod_arr = self.tree_html.xpath("//div[@class='prod-tag-descrip']")
            long_description.append(span_item)
            for prod_item in prod_arr:
                h4 = prod_item.xpath(".//h4//text()")[0]
                if h4 == span_item:
                    p_txt = prod_item.xpath(".//p//text()")[0].strip()
                    long_description.append(p_txt)

        long_description = "\n".join(long_description).strip()
        return long_description

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    #returns 1 if the mobile version is the same, 0 otherwise
    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        image_url = self.tree_html.xpath("//img[@itemprop='image']/@src")
        return image_url

    def _image_count(self):
        image_urls = self._image_urls()
        return len(image_urls)

    def _video_urls(self):
        return None

    def _video_count(self):
        urls = self._video_urls()
        if urls:
            return len(urls)
        return 0

    def _pdf_urls(self):
        pdfs = self.tree_html.xpath("//a[contains(@href,'.pdf')]")
        pdf_hrefs = []
        for pdf in pdfs:
            if pdf.attrib['title'] == 'Terms & Conditions':
                pass
            else:
                pdf_hrefs.append(pdf.attrib['href'])
        if len(pdf_hrefs) == 0:
            return None
        return pdf_hrefs

    def _pdf_count(self):
        urls = self._pdf_urls()
        if urls is not None:
            return len(urls)
        return 0

    def _webcollage(self):
        return 0

    # extract htags (h1, h2) from its product product page tree
    def _htags(self):
        htags_dict = {}
        # add h1 tags text to the list corresponding to the "h1" key in the dict
        htags_dict["h1"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h1//text()[normalize-space()!='']"))
        # add h2 tags text to the list corresponding to the "h2" key in the dict
        htags_dict["h2"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h2//text()[normalize-space()!='']"))
        return htags_dict

    def _keywords(self):
        return self.tree_html.xpath("//meta[@name='keywords']/@content")[0]

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################
    def _average_review(self):
        script = self.tree_html.xpath("//script//text()")
        script = " ".join(script)
        m = re.findall(r"setAvgRating\(([0-9\.]+)\);", script)
        average_review = m[0]
        return float(average_review)

    def _review_count(self):
        try:
            review_count = self.tree_html.xpath("//div[@itemprop='ratingValue']//@title")[0]
            m = re.findall(r"[0-9]+", review_count)
            return int(m[0])
        except IndexError:
            return 0

    def _max_review(self):
        return None

    def _min_review(self):
        return None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath("//meta[starts-with(@property,'og:price:amount')]/@content")[0].strip()
        return price

    def _in_stores_only(self):
        return None

    def _in_stores(self):
        return None

    def _owned(self):
        return 1
    
    def _marketplace(self):
        return 0

    def _owned_out_of_stock(self):
        availability = self.tree_html.xpath("//span[@itemprop='availability']")
        if len(availability) > 0:
            return 0
        return 1

    def _marketplace_sellers(self):
        return None

    def _marketplace_lowest_price(self):
        return None

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        return self.tree_html.xpath("//ul[@class='shop-map']/li[starts-with(@class,'active')]/a/text()")

    def _category_name(self):
        return self._categories()[-1]

    def _brand(self):
        return self.tree_html.xpath("//a[@itemprop='brand']//text()")[0].strip()

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces
    def _clean_text(self, text):
        return re.sub("&nbsp;", " ", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################
    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service
    DATA_TYPES = { \
        # CONTAINER : NONE
        "url" : _url, \
        "product_id" : _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "features" : _features, \
        "feature_count" : _feature_count, \
        "description" : _description, \
        "model" : _model, \
        "long_description" : _long_description, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls, \
        "image_count" : _image_count, \
        "video_urls" : _video_urls, \
        "video_count" : _video_count, \
        "webcollage" : _webcollage, \
        "htags" : _htags, \
        "keywords" : _keywords, \
        "pdf_urls" : _pdf_urls, \
        "pdf_count" : _pdf_count, \
        "mobile_image_same" : _mobile_image_same, \

        # CONTAINER : REVIEWS
        "average_review" : _average_review, \
        "review_count" : _review_count, \
        "max_review" : _max_review, \
        "min_review" : _min_review, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "in_stores_only" : _in_stores_only, \
        "in_stores" : _in_stores, \
        "owned" : _owned, \
        "owned_out_of_stock" : _owned_out_of_stock, \
        "marketplace": _marketplace, \
        "marketplace_sellers" : _marketplace_sellers, \
        "marketplace_lowest_price" : _marketplace_lowest_price, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "category_name" : _category_name, \
        "loaded_in_seconds": None \
        }


    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = { \
        # CONTAINER : CLASSIFICATION
        "brand" : _brand, \
    }

