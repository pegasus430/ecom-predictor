#!/usr/bin/python
#  -*- coding: utf-8 -*-

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


class DrugstoreScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www\.drugstore\.com/([a-zA-Z0-9\-]+)/(.*)"

    reviews_tree = None
    max_score = None
    min_score = None
    review_count = None
    average_review = None
    reviews = None
    image_urls = None
    image_count = None

    def check_url_format(self):
        # for ex: http://www.drugstore.com/california-exotic-novelties-up--tighten-it-up-v-gel/qxp450311?catid=181966
        m = re.match(r"^http://www\.drugstore\.com/([a-zA-Z0-9\-]+)/(.*)", self.product_page_url)
        return not not m

    def not_a_product(self):
        '''Overwrites parent class method that determines if current page
        is not a product page.
        Currently for Amazon it detects captcha validation forms,
        and returns True if current page is one.
        '''

        if len(self.tree_html.xpath("//h1[@class='captionText']/text()")) < 1:
            return True
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _url(self):
        return self.product_page_url

    def _product_id(self):
        product_id = self.tree_html.xpath("//input[@name='product']/@value")[0].strip()
        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath("//h1[@class='captionText']//text()")[0].strip()

    def _product_title(self):
        return self.tree_html.xpath("//h1[@class='captionText']//text()")[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath("//title//text()")[0].strip()
    
    def _model(self):
        return None

    def _upc(self):
        return None

    def _features(self):
        line_txts = []
        all_features_text = line_txts
        if len(all_features_text) < 1:
            return None
        return all_features_text

    def _feature_count(self):
        features = len(self._features())
        if features is None:
            return 0
        return len(self._features())

    def _model_meta(self):
        return None

    def _description(self):
        description = self._description_helper()
        if description is None or len(description) < 1:
            return self._long_description_helper()
        return description

    def _description_helper(self):
        rows = self.tree_html.xpath("//div[@id='divSellCopy']//text()")
        rows = [self._clean_text(r) for r in rows if len(self._clean_text(r)) > 0]
        description = "\n".join(rows)
        if len(description) < 1:
            return None
        return description

    def _long_description(self):
        description = self._description_helper()
        if description is None or len(description) < 1:
            return None
        return self._long_description_helper()

    def _long_description_helper(self):
        rows = self.tree_html.xpath("//table[@id='TblProdForkPromo']//text()")
        rows = [self._clean_text(r) for r in rows if len(self._clean_text(r)) > 0]
        description = "\n".join(rows)
        if len(description) < 1:
            return None
        return description

    def _ingredient_count(self):
        if self._ingredients():
            return len(self._ingredients())
        return 0

    def _ingredients(self):
        ingredient_list = []

        rows = self.tree_html.xpath('//table[@id="TblProdForkIngredients"]//text()')
        for row in rows:
            if 'Ingredients' in row:
                continue

            ingredient_list += map( self._clean_text, row.split(':')[-1].split(','))

        if ingredient_list:
            return ingredient_list

    def _variants(self):
        variants = []

        tree_html = self.tree_html

        for variant_link in self.tree_html.xpath('//a[@class="groupDistinction"]'):
            variant_url = 'http://www.drugstore.com' + variant_link.xpath('@href')[0]
            variant = variant_link.xpath('text()')[0]
            selected = True

            # temporarily get variant tree html
            if not variant_url.split('?')[0] == self._canonical_link():
                variant_html = html.fromstring( self.load_page_from_url_with_number_of_retries( variant_url))

                self.tree_html = variant_html

                selected = False

            # make sure tree_html gets reset if there is some exception
            try:
                image_url = None
                if self._image_urls():
                    image_url = self._image_urls()[0]

                variants.append( {
                    "in_stock" : self._in_stock() == 1,
                    "properties" : {
                        "variant" : variant
                    },
                    "price" : self._price(),
                    "selected" : selected,
                })
            except:
                self.tree_html = tree_html
                raise

            self.tree_html = tree_html

        if len(variants) > 1:
            return variants

    def _swatches(self):
        swatches = []

        for distinction in self.tree_html.xpath('//div[@id="divDistinctionBtnType"]'):
            onmouseover = distinction.xpath('@onmouseover')

            # If there is no mouseover, that swatch is not available for this variant
            if not onmouseover:
                continue

            s = {
                "color": re.search("'([^']+)'\)", onmouseover[0]).group(1),
                "hero": 1,
                "hero_image": [
                    re.search("'(http://[^']+)'", onmouseover[0]).group(1)
                ],
                "swatch_name": "color",
                "thumb": 1,
                "thumb_image": [
                  re.search('(http://[^\)]+)\)', distinction.xpath('@style')[0]).group(1)
                ]
              }

            swatches.append(s)

        if swatches:
            return swatches

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _canonical_link(self):
        return self.tree_html.xpath('//link[@rel="canonical"]/@href')[0]

    #returns 1 if the mobile version is the same, 0 otherwise
    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        if self.image_count is not None:
            return self.image_urls
        self.image_count = 0

        url = self.tree_html.xpath("//div[@id='divPImage']//a/@href")[0].strip()
        m = re.findall(r"javascript:popUp\('(.*?)',", url)
        url = "http://www.drugstore.com%s" % m[0]
        redirect_contents = urllib.urlopen(url).read()
        redirect_tree = html.fromstring(redirect_contents)

        image_url = []
        loop_flag = True
        while loop_flag:
            image_url.append(redirect_tree.xpath("//div[@id='productImage']//img/@src")[0].strip())
            try:
                redirect_url = redirect_tree.xpath("//td[@align='left']//a/@href")[0].strip()
                redirect_url = "http://www.drugstore.com/%s" % redirect_url
                redirect_contents = urllib.urlopen(redirect_url).read()
                redirect_tree = html.fromstring(redirect_contents)
            except IndexError:
                loop_flag = False

        self.image_urls = image_url
        if len(image_url) < 1:
            return None
        self.image_count = len(image_url)
        return image_url

    def _image_count(self):
        if self.image_count is None:
            self.image_urls()
        return self.image_count

    def _video_urls(self):
        video_url = []
        if len(video_url) < 1:
            return None
        return video_url

    def _video_count(self):
        urls = self._video_urls()
        if urls:
            return len(urls)
        return 0

    def _pdf_urls(self):
        pdfs = self.tree_html.xpath("//a[contains(@href,'.pdf')]")
        pdf_hrefs = []
        for pdf in pdfs:
            pdf_hrefs.append(pdf.attrib['href'])

        if pdf_hrefs:
            return pdf_hrefs

    def _pdf_count(self):
        urls = self._pdf_urls()
        if urls is not None:
            return len(urls)
        return 0

    def _webcollage(self):
        atags = self.tree_html.xpath("//a[contains(@href, 'webcollage.net/')]")
        if len(atags) > 0:
            return 1
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
    #populate the reviews_tree variable for use by other functions
    def _load_reviews(self):
        if not self.max_score or not self.min_score:
            rows = self.tree_html.xpath("//ul[contains(@class,'pr-ratings-histogram-content')]//li//p[@class='pr-histogram-count']//text()")
            self.reviews = []
            idx = 5
            rv_scores = []
            for row in rows:
                cnt = int(re.findall(r"\d+", row)[0])
                if cnt > 0:
                    self.reviews.append([idx, cnt])
                    rv_scores.append(idx)
                else:
                    self.reviews.append([idx, cnt])
                idx -= 1
                if idx < 1:
                    break
            self.max_score = max(rv_scores)
            self.min_score = min(rv_scores)

    def _average_review(self):
        avg_review = self.tree_html.xpath("//span[contains(@class,'average')]//text()")[0].strip()
        avg_review = round(float(avg_review), 2)
        return avg_review

    def _review_count(self):
        review_cnt = self.tree_html.xpath("//span[@class='count']//text()")[0].strip()
        return int(review_cnt)

    def _max_review(self):
        self._load_reviews()
        return self.max_score

    def _min_review(self):
        self._load_reviews()
        return self.min_score

    def _reviews(self):
        self._load_reviews()
        return self.reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath("//span[@itemprop='price']//text()")[0].strip()
        return price

    def _price_amount(self):
        price = self._price()
        price = price.replace(",", "")
        price_amount = re.findall(r"[\d\.]+", price)[0]
        return float(price_amount)

    def _price_currency(self):
        price = self._price()
        price = price.replace(",", "")
        price_amount = re.findall(r"[\d\.]+", price)[0]
        price_currency = price.replace(price_amount, "")
        if price_currency == "$":
            return "USD"
        return price_currency

    def _in_stores(self):
        return None

    def _marketplace(self):
        return 0

    def _marketplace_sellers(self):
        return None

    def _marketplace_lowest_price(self):
        return None

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self._site_online() == 0:
            return None
        rows = self.tree_html.xpath("//div[@id='ReplacementReasonDiv']//text()")
        for row in rows:
            if "temporarily out of stock" in row:
                return 1
        return 0

    def _in_stores_out_of_stock(self):
        '''in_stores_out_of_stock - currently unavailable for pickup from a physical store - binary
        (null should be used for items that can not be ordered online and the availability may depend on location of the store)
        '''
        return None

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        all = self.tree_html.xpath("//div[@id='divBreadCrumb']//a[@class='breadcrumb']//text()")
        out = [self._clean_text(r) for r in all]
        if out[0].lower() == "home":
            out = out[1:]
        if len(out) < 1:
            return None
        return out

    def _category_name(self):
        return self._categories()[-1]

    def _brand(self):
        brandstore = self.tree_html.xpath('//a[@class="brandstore"]/@href')
        if brandstore:
            return re.match('/([^/]+)/', brandstore[0]).group(1)

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
        "ingredient_count" : _ingredient_count, \
        "ingredients" : _ingredients, \
        "variants" : _variants, \
        "swatches" : _swatches, \

        # CONTAINER : PAGE_ATTRIBUTES
        "canonical_link" : _canonical_link, \
        "video_urls" : _video_urls, \
        "video_count" : _video_count, \
        "webcollage" : _webcollage, \
        "htags" : _htags, \
        "keywords" : _keywords, \
        "mobile_image_same" : _mobile_image_same, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "price_amount" : _price_amount, \
        "price_currency" : _price_currency, \
        "in_stores" : _in_stores, \
        "marketplace": _marketplace, \
        "marketplace_sellers" : _marketplace_sellers, \
        "marketplace_lowest_price" : _marketplace_lowest_price, \
        "site_online" : _site_online, \
        "site_online_out_of_stock" : _site_online_out_of_stock, \
        "in_stores_out_of_stock" : _in_stores_out_of_stock, \

         # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \
        "max_review" : _max_review, \
        "min_review" : _min_review, \
        "reviews" : _reviews, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "category_name" : _category_name, \
        "brand" : _brand, \

        "loaded_in_seconds": None \
        }


    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = { \
        # CONTAINER : CLASSIFICATION
        # CONTAINER : PAGE_ATTRIBUTES
        "pdf_urls" : _pdf_urls, \
        "pdf_count" : _pdf_count, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls, \
        "image_count" : _image_count, \
    }

