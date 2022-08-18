#!/usr/bin/python

import re
import traceback
import json
import requests

from extract_data import Scraper


class AsdaScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    API_URL = 'https://groceries.asda.com/api/items/view?itemid={}' \
                  '&responsegroup=extended' \
                  '&cacheable=true' \
                  '&shipdate=currentDate' \
                  '&requestorigin=gi'

    REVIEW_URL = "https://groceries.asda.com/review/reviews.json?Filter=ProductId:{}" \
                 "&Sort=SubmissionTime:desc" \
                 "&apiversion=5.4" \
                 "&passkey=92ffdz3h647mtzgbmu5vedbq" \
                 "&Offset=0" \
                 "&Limit={}"

    IMAGE_URL_API = '{host}asdagroceries/{asset_id}?req=set,json,UTF-8'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = {}
        self.images_checked = False
        self.image_urls = []
        self._set_proxy()

    def _extract_page_tree(self):
        for i in range(3):
            try:
                self.session = requests.session()
                item_id = re.search('/(\d+)$', self.product_page_url).group(1)
                product_url = self.API_URL.format(item_id)
                self.product_json = self._request(product_url, session=self.session).json()
                return
            except Exception as e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', str(e))

    def not_a_product(self):
        if not self.product_json:
            return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self._sku()

    def _sku(self):
        return self.product_json["items"][0]["id"]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        item = self.product_json["items"][0]
        if item.get('weight'):
            name = "{} {}".format(item['name'], item.get('weight', ''))
        else:
            name = item['name']
        return name

    def _upc(self):
        return self.product_json["items"][0]["upcNumbers"][0]["upcNumber"]

    def _product_code(self):
        return self.product_json["items"][0]["cin"]

    def _features(self):
        if self.product_json["items"][0]["productDetails"].get("featuresformatted", None):
            features_string = self.product_json["items"][0]["productDetails"]["featuresformatted"]
            features_string_list = features_string.split(". ")

            return features_string_list

    def _nutrition_facts(self):
        if self.product_json["items"][0]["productDetails"].get("nutritionalValues", None):
            nutrition_json = self.product_json["items"][0]["productDetails"]["nutritionalValues"]["values"]
            nutrition_string_list = []

            for nutrition in nutrition_json:
                nutrition_string_list.append(nutrition["value1"] + " " + nutrition["value2"] + " " + nutrition["value3"])

            return nutrition_string_list

    def _description(self):
        short_description = ""

        if len(self.product_json["items"][0]["description"]) > 1:
            short_description = self.product_json["items"][0]["description"].strip()

        if self.product_json["items"][0]["productDetails"]["furtherDesc"]:
            short_description += '<h4 class="sect-title">Further Description</h4>'
            short_description += ('<p class="p-text">' + self.product_json["items"][0]["productDetails"]["furtherDesc"])\
                                  + '</p>'

        if short_description.strip():
            return short_description

    def _long_description(self):
        long_description = ""

        if self.product_json["items"][0]["productDetails"]["productMarketing"]:
            long_description += '<h4 class="sect-title">Product Marketing</h4>'
            long_description += ('<p class="p-text">' + self.product_json["items"][0]["productDetails"]["productMarketing"])\
                                  + '</p>'

        if self.product_json["items"][0]["productDetails"]["brandMarketing"]:
            long_description += '<h4 class="sect-title">Brand Marketing</h4>'
            long_description += ('<p class="p-text">' + self.product_json["items"][0]["productDetails"]["brandMarketing"])\
                                  + '</p>'

        if self.product_json["items"][0]["productDetails"]["manufacturerMarketing"]:
            long_description += '<h4 class="sect-title">Manufacturer Marketing</h4>'
            long_description += ('<p class="p-text">' + self.product_json["items"][0]["productDetails"]["manufacturerMarketing"])\
                                  + '</p>'

        if self.product_json["items"][0]["productDetails"]["safetyWarning"]:
            long_description += '<h4 class="sect-title">Safety Warning</h4>'
            long_description += ('<p class="p-text">' + self.product_json["items"][0]["productDetails"]["safetyWarning"])\
                                  + '</p>'

        if self.product_json["items"][0]["productDetails"]["otherInfo"]:
            long_description += '<h4 class="sect-title">Other information</h4>'
            long_description += ('<p class="p-text">' + self.product_json["items"][0]["productDetails"]["otherInfo"])\
                                  + '</p>'

        if self.product_json["items"][0]["productDetails"]["preparationUsage"]:
            long_description += '<h4 class="sect-title">Preparation and Usage</h4>'
            long_description += ('<p class="p-text">' + self.product_json["items"][0]["productDetails"]["preparationUsage"])\
                                  + '</p>'

        if long_description.strip():
            return long_description

    def _ingredients(self):
        ingredients = None

        if len(self.product_json["items"][0]["productDetails"]["ingredients"]) == 0:
            return None

        ingredients = self.product_json["items"][0]["productDetails"]["ingredients"][1:-1]

        ingredients = ingredients.split(",")

        return ingredients

    def _manufacturer(self):
        if not self._ingredients():
            return 0

        if self.product_json["items"][0]["productDetails"].get("manufacturerPath", None):
            return self.product_json["items"][0]["productDetails"]["manufacturerPath"]

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        if self.images_checked:
            return self.image_urls
        self.images_checked = True
        resp = self._request(
            self.IMAGE_URL_API.format(
                host=self.product_json["items"][0]["scene7Host"],
                asset_id=self.product_json["items"][0]["scene7AssetId"]
            ),
            session=self.session
        )
        if resp.status_code == 200:
            try:
                data = re.search(r's7jsonResponse\(({.*?}),""\);', resp.text)
                if data:
                    data = json.loads(data.group(1)).get('set', {})
                    if data.get('item'):
                        items = data.get('item') if isinstance(data.get('item'), list) else [data.get('item')]
                        self.image_urls = [
                            self.product_json["items"][0]["scene7Host"] + i.get('i', {}).get('n')
                            for i in items
                            if i.get('i', {}).get('n')
                        ]
            except Exception as e:
                print traceback.format_exc()
                if self.lh:
                    self.lh.add_list_log('errors', str(e))
        if not self.image_urls:
            self.image_urls = [next(iter(self.product_json.get("items")), {}).get("images", {}).get("largeImage")]
        return self.image_urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.product_json["items"][0]["price"]
        return price

    def _price_currency(self):
        return "GBP"

    def _in_stores(self):
        if self.product_json["items"][0]["availability"] == "A":
            return 1

        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = [
            self.product_json["items"][0]["deptName"],
            self.product_json["items"][0]["aisleName"],
            self.product_json["items"][0]["shelfName"]
        ]
        return categories

    def _brand(self):
        return self.product_json["items"][0]["brandName"]

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        if self._review_count():
            avg_review = self.product_json["items"][0]["avgStarRating"]
            return round(float(avg_review), 1)

    def _review_count(self):
        review_count = self.product_json["items"][0]["totalReviewCount"]
        return int(review_count)

    def _reviews(self):
        if self.is_review_checked:
            return self.reviews

        self.is_review_checked = True

        total_count = self._review_count()

        if total_count == 0:
            return

        results = []

        remain_count = total_count

        for i in range(0, total_count/100 + 1):
            limit = 100 if remain_count/100 > 0 else remain_count % 100

            review_url = self.REVIEW_URL.format(self._sku(), limit)
            review_json = self._request(review_url, session=self.session).json()

            remain_count -= limit

            results += review_json["Results"]

        self.reviews = [[5, 0], [4, 0], [3, 0], [2, 0], [1, 0]]

        for review in results:
            self.reviews[5 - review['Rating']][1] += 1

        return self.reviews

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,
        "sku": _sku,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_code": _product_code,
        "upc": _upc,
        "features": _features,
        "description": _description,
        "long_description": _long_description,
        "ingredients": _ingredients,
        "manufacturer": _manufacturer,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : REVIEWS
        "review_count": _review_count,
        "average_review": _average_review,
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "price": _price,
        "price_currency": _price_currency,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
