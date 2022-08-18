#!/usr/bin/python

import urllib
import re
import sys
import json
import copy

from lxml import html, etree
import time
import requests
from extract_data import Scraper


class ZulilyScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.zulily.com/p/<product-name>/<product-id>"
    REVIEW_URL = "http://zulily.ugc.bazaarvoice.com/1999aa/{0}/reviews.djs?format=embeddedhtml"
    LOG_IN_URL = "https://www.zulily.com/auth"
    SITE_URL = "http://www.zulily.com"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        # whether product has any webcollage media
        self.product_json = None
        # whether product has any webcollage media
        self.review_json = None
        self.review_list = None
        self.is_review_checked = False

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://www.zulily.com/p/.*?$", self.product_page_url)
        return not not m

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """
        try:
            itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')[0].strip()

            if itemtype.lower() != "product":
                raise Exception()

        except Exception:
            arr = self.tree_html.xpath('//div[@id="productinfo_ctn"]//div[contains(@class,"error")]//text()')
            if "to view is not currently available." in " ".join(arr).lower():
                return False
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_page_tree(self):
        """Overwrites parent class method that builds and sets as instance variable the xml tree of the product page
        Returns:
            lxml tree object
        """
        agent = 'Mozilla/5.0 (X11; Linux x86_64; rv:24.0) Gecko/20140319 Firefox/24.0 Iceweasel/24.4.0'

        #Set login form for delivery
        ##TODO replace this account with new one
        payload = '{"login": {"username": "arnoldmessi777@gmail.com", "password": "apple123"}, ' \
               '"redirectUrl": "https://www.zulily.com/"}'
        headers ={'Content-Type': 'application/json;charset=UTF-8', 'User-agent': agent}

        for i in range(self.MAX_RETRIES):
            # Use 'with' to ensure the session context is closed after use.
            with requests.Session() as s:
                s.post(self.LOG_IN_URL, data=payload)
                # An authorised request.
                response = s.get(self.product_page_url,headers=headers, timeout=5)
                if self.lh:
                    self.lh.add_log('status_code', response.status_code)
                if response != 'Error' and response.ok:
                    contents = response.text
                    try:
                        self.tree_html = html.fromstring(contents.decode("utf8"))
                    except UnicodeError, e:
                        # if string was not utf8, don't deocde it
                        print "Warning creating html tree from page content: ", e.message
                        self.tree_html = html.fromstring(contents)
                    return

    def _extract_product_json(self):
        if self.product_json:
            return

        product_json = {"id_json": {}, "event_data": {}, "style_data": {}}

        try:
            id_json = self.tree_html.xpath("//script[@type='application/ld+json']/text()")[0].strip()
            product_json["id_json"] = json.loads(id_json)
        except Exception as e:
            print "Parsing issue in id_json.", e.message

        page_raw_text = html.tostring(self.tree_html)
        try:
            event_data = re.findall(r'window.eventData =(.+);\n\twindow.styleData =', page_raw_text)[0]
            product_json["event_data"] = json.loads(event_data)
        except Exception as e:
            print "Parsing issue in even_data.", e.message

        try:
            style_data = re.findall(r'window.styleData =(.+);\n', page_raw_text)[0]
            product_json["style_data"] = json.loads(style_data)
        except Exception as e:
            print "Parsing issue in style_data.", e.message

        self.product_json = product_json

        return product_json

    def _canonical_link(self):
        canonical_link = self.tree_html.xpath("//link[@rel='canonical']/@href")[0]

        return canonical_link

    def _url(self):
        return self.product_page_url

    def _event(self):
        return None

    def _product_id(self):
        return self.product_json['style_data']['id']

    def _site_id(self):
        return None

    def _status(self):
        return "success"

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.product_json.get("id_json", {}).get("name")

    def _product_title(self):
        return self.product_json.get("id_json", {}).get("name")

    def _title_seo(self):
        return self.product_json.get("id_json", {}).get("name")

    def _model(self):
        return self.product_json.get("info", {}).get("modelNumber")

    def _upc(self):
        scripts = self.tree_html.xpath('//script//text()')
        for script in scripts:
            var = re.findall(r'CI_ItemUPC=(.*?);', script)
            if len(var) > 0:
                var = var[0]
                break
        var = re.findall(r'[0-9]+', str(var))[0]
        return var

    def _features(self):
        features_td_list = self.tree_html.xpath('//table[contains(@class, "tablePod tableSplit")]//td')
        features_list = []

        for index, val in enumerate(features_td_list):
            if (index + 1) % 2 == 0 and features_td_list[index - 1].xpath(".//text()")[0].strip():
                features_list.append(features_td_list[index - 1].xpath(".//text()")[0].strip() + " " + features_td_list[index].xpath(".//text()")[0].strip())

        if features_list:
            return features_list

        return None

    def _feature_count(self):
        if self._features():
            return len(self._features())

        return None

    def _model_meta(self):
        return None

    def _description(self):
        return self.product_json.get("style_data", {}).get("descriptionHtml")

    def _shelf_description(self):
        return self.product_json.get("event_data", {}).get("descriptionHtml")

    def _long_description(self):
        return self.product_json.get("style_data", {}).get("descriptionHtml")

    def _swatches(self):
        swatches = []

        for img in self.tree_html.xpath('//div[contains(@class, "sku_variant")]/ul/li/a/img'):
            swatch = {
                'color' : img.get('title'),
                'hero' : 1,
                'hero_image' : img.get('src')
            }
            swatches.append(swatch)

        if swatches:
            return swatches

    def _variants(self):
        variants = []

        first_sku_variant = True

        for sku_variant in self.tree_html.xpath('//div[contains(@class, "sku_variant")]'):
            variants = []

            for option in sku_variant.xpath('ul/li'):
                if 'product_sku_Overlay_ColorSwatch' in sku_variant.get('class'):
                    v = {
                        'selected' : False,
                        'properties' : {
                            'color' : option.xpath('a/img/@title')[0]
                        }
                    }

                    if option.get('class') and 'selected' in option.get('class'):
                        v['selected'] = True

                else:
                    custom_label = sku_variant.xpath('a[@class="customLabel"]/text()')[0]
                    selected_value = sku_variant.xpath('a[@class="customLabel"]/span[contains(@class,"select")]/text()')[0]

                    value = option.xpath('a/text()')[0]

                    v = {
                        'selected' : selected_value == value,
                        'properties' : {
                            custom_label : value
                        }
                    }

                if not first_sku_variant:
                    for variant in original_variants:
                        variant_copy = copy.deepcopy(variant)
                        variant_copy['properties'].update(v['properties'])
                        if not v['selected']:
                            variant_copy['selected'] = False
                        variants.append(variant_copy)

                else:
                    variants.append(v)

            original_variants = copy.deepcopy(variants)
            first_sku_variant = False

        if variants:
            return variants

    def _no_longer_available(self):
        arr = self.tree_html.xpath('//div[@id="productinfo_ctn"]//div[contains(@class,"error")]//text()')
        if "to view is not currently available." in " ".join(arr).lower():
            return 1
        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        return None

    def _image_urls(self):        
        media_list = self.product_json.get("style_data", {}).get("gallery")
        image_list = []

        for media_item in media_list:
                image_list.append(self.SITE_URL + media_item)

        if image_list:
            return image_list

        return None

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    def _video_urls(self):
        return None

    def _video_count(self):
        return 0

    def _pdf_urls(self):
        return None

    def _pdf_count(self):
        return 0

    def _webcollage(self):
        return None

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
        if self._review_count() == 0:
            return None

        average_review = round(float(self.review_json.get("jsonData", {}).get("attributes", {}).get("avgRating")), 1)

        if str(average_review).split('.')[1] == '0':
            return int(average_review)
        else:
            return float(average_review)

    def _review_count(self):
        self._reviews()

        if not self.review_json:
            return 0

        return int(self.review_json.get("jsonData", {}).get("attributes", {}).get("numReviews"))

    def _max_review(self):
        if self._review_count() == 0:
            return None

        for i, review in enumerate(self.review_list):
            if review[1] > 0:
                return 5 - i

    def _min_review(self):
        if self._review_count() == 0:
            return None

        for i, review in enumerate(reversed(self.review_list)):
            if review[1] > 0:
                return i + 1

    def _reviews(self):
        return None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        return self.product_json.get("style_data", {}).get("price")

    def _price_amount(self):
        return float( self._price()[1:].replace(',',''))

    def _price_currency(self):
        return self.product_json.get("style_data", {}).get("currency")

    def _temp_price_cut(self):
        return self.product_json.get("itemExtension", {}).get("localStoreSku", {}).get("pricing", {}).get("itemOnSale")

    def _in_stores(self):
        self._extract_product_json()

        availability = self.tree_html.xpath("//meta[@property='og:availability']/@content")
        if availability:
            avail = True if availability[0] == 'instock' else False
            return avail

        return True

    def _site_online(self):
        self._extract_product_json()
        '''
        if self.product_json["itemAvailability"]["availableOnlineStore"] == True:
            return 1
        '''
        return 1

    def _site_online_out_of_stock(self):
        availability = self.tree_html.xpath("//meta[@property='og:availability']/@content").extract()
        if availability:
            no_longer_avail = False if availability[0] == 'instock' else True
            return no_longer_avail

        return 0

    def _in_stores_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    def _marketplace_sellers(self):
        return None

    def _marketplace_lowest_price(self):
        return None

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        scripts = self.tree_html.xpath('//script//text()')
        for script in scripts:
            jsonvar = re.findall(r'BREADCRUMB_JSON = (.*?});', script)
            if len(jsonvar) > 0:
                jsonvar = jsonvar[0]
                break
        jsonvar = json.loads(jsonvar)
        all = jsonvar['bcEnsightenData']['contentSubCategory'].split(u'\u003e')
        return all

    def _category_name(self):
        return self._categories()[-1]
    
    def _brand(self):
        self._extract_product_json()

        return self.product_json.get("info", {}).get("brandName")


    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces
    def _clean_text(self, text):
        return re.sub("[\n\t]", "", text).strip()


    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "url" : _url, \
        "event" : _event, \
        "product_id" : _product_id, \
        "site_id" : _site_id, \
        "status" : _status, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "model" : _model, \
        "upc" : _upc,\
        "features" : _features, \
        "feature_count" : _feature_count, \
        "model_meta" : _model_meta, \
        "description" : _description, \
        "long_description" : _long_description, \
        "swatches" : _swatches, \
        "variants" : _variants, \
        "no_longer_available" : _no_longer_available, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count" : _image_count,\
        "image_urls" : _image_urls, \
        "video_count" : _video_count, \
        "video_urls" : _video_urls, \
        "pdf_count" : _pdf_count, \
        "pdf_urls" : _pdf_urls, \
        "webcollage" : _webcollage, \
        "htags" : _htags, \
        "keywords" : _keywords, \
        "canonical_link": _canonical_link,

        # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \
        "max_review" : _max_review, \
        "min_review" : _min_review, \
        "reviews" : _reviews, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "price_amount" : _price_amount, \
        "price_currency" : _price_currency, \
        "temp_price_cut" : _temp_price_cut, \
        "in_stores" : _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "in_stores_out_of_stock": _in_stores_out_of_stock, \
        "marketplace" : _marketplace, \
        "marketplace_sellers" : _marketplace_sellers, \
        "marketplace_lowest_price" : _marketplace_lowest_price, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "category_name" : _category_name, \
        "brand" : _brand, \

        "loaded_in_seconds" : None, \
        }

    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = { \
        "mobile_image_same" : _mobile_image_same, \
        "shelf_description": _shelf_description, \
    }
