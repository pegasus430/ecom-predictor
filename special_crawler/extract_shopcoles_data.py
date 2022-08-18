#!/usr/bin/python

import re
import requests
import HTMLParser
import traceback
import json
from lxml import html

from extract_data import Scraper


class ShopColesScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://shop.coles.com.au/.*/product/<product-name>"

    API_URL = "https://shop.coles.com.au/search/resources/store/20601/productview/bySeoUrlKeyword/{product_name}?catalogId=10576"

    product_json = {}

    def check_url_format(self):
        m = re.match(r"^https?://shop.coles.com.au/.*$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        self.extract_product_json()
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def extract_product_json(self):
        headers = {'User-Agent': self.select_browser_agents_randomly()}
        product_name = re.search('/product/(.+)', self.product_page_url)
        try:
            if product_name:
                product_name = product_name.group(1)
                api_url = self.API_URL.format(product_name=product_name)
                json = requests.get(api_url, headers=headers, timeout=10).json()
                self.product_json = json["catalogEntryView"][0]

        except:
            print traceback.format_exc()

    def _product_id(self):
        if self.product_json:
            return self.product_json["p"]
        else:
            product_id = re.search('\d+', self.tree_html.xpath("//p[@class='sku']/text()")[0])

        return product_id.group() if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _brand(self):
        if self.product_json:
            return self.product_json["m"]

    def _product_name(self):
        if self.product_json:
            title = self.product_json['n']
            try:
                weight = ''.join(self.product_json['a']['O3'])
            except:
                weight = None
            if weight:
                return title + '-' + weight
            else:
                return title
        else:
            product_name = self.tree_html.xpath("//h1[@class='productName']/text()")
        return product_name[0] if product_name else None

    def _features(self):
        if self.product_json:
            if "F" in self.product_json["a"]:
                return self.product_json["a"]["F"][0]

    def _description(self):
        if self.product_json:
            return self.product_json["l6"]
        else:
            description = self.tree_html.xpath("//p[@class='productLongDescription']/following-sibling::*[1]/text()")
        return description[0] if description else None

    def _no_longer_available(self):
        if 'a6' in self.product_json:
            return 1
        return 0

    def _ingredients(self):
        ingredients = None

        if self.product_json:
            ingredients_info = self.product_json['a']['I']
        else:
            ingredients_info = self.tree_html.xpath("//div[@class='attribute']")[0].xpath(".//p/text()")

        if ingredients_info:
            ingredients = ingredients_info[0].split(',')

        if ingredients:
            ingredients = map(lambda x: self._clean_text(x), ingredients)
            ingredients = filter(len, ingredients)

        return ingredients

    def _nutrition_facts(self):
        nutriton_facts = []
        fact_rows = []
        for key, value in self.product_json.get('a', {}).iteritems():
            if 'N' in key and value:
                fact_rows.append([key, value[0]])

        if not fact_rows:
            return None

        facts_info = None
        try:
            facts_info = re.search(r"'minificationCodes':(.*})", html.tostring(self.tree_html)).group(1)
            facts_info = json.loads(facts_info)
        except:
            print traceback.format_exc()

        if not facts_info:
            return None

        for fact_row in fact_rows:
           nutriton_facts.append(facts_info[fact_row[0]].replace('NUTRIENT', '') + ":" + fact_row[1])

        return nutriton_facts

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_list = []
        if self.product_json:
            image_url = self.product_json["fi"]
        else:
            image_url = self.tree_html.xpath("//div[@class='productImage']//img/@src")
            if image_url:
                image_url = image_url[0]

        if image_url:
            image_url = "https://shop.coles.com.au" + image_url
            image_list.append(image_url)

        if image_list:
            return image_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        if self.product_json:
            return float(self.product_json["p1"]["o"])
        else:
            price_amount = self.tree_html.xpath("//p[@class='price']/text()")
        return float(price_amount[0]) if price_amount else None

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self._no_longer_available():
            return 1
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        if self.product_json:
            return self.product_json['a']['P8']

    def _manufacturer(self):
        if self.product_json:
            return self.product_json["m"]

    def _clean_text(self, text):
        text = HTMLParser.HTMLParser().unescape(text)
        text = re.sub('[\r\n\t]', '', text)
        text = re.sub('>\s+<', '><', text)
        return re.sub('\s+', ' ', text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "brand": _brand,
        "product_name" : _product_name,
        "features" : _features,
        "description" : _description,
        "ingredients": _ingredients,
        "no_longer_available": _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,

        # CONTAINER : SELLERS
        "price_amount" : _price_amount,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,
        "marketplace" : _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "manufacturer" : _manufacturer,
        }
