#!/usr/bin/python

import re
import traceback
from lxml import html

from extract_data import Scraper


class WebGrocerScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = 'Expected URL format is http(s)://{}/store/<store-id>(/)#/product/sku/<product-id>'

    API_URL = 'https://{0}/api/product/v7/chains/865751/stores/{1}/skus/{2}'

    NUTRITION_URL = 'https://{0}/api/product/v7/product/{1}/store/{2}/nutrition'

    HEADERS = {
        "Accept": "application/vnd.mywebgrocer.product+json",
        "Authorization": None
    }

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.store_id = None
        self.product_id = None
        self.product_json = None
        self.nutrition_html = None

    def check_url_format(self):
        self.INVALID_URL_MESSAGE = self.INVALID_URL_MESSAGE.format(self.SITE)

        m = re.match('https?://{}/store/(.*?)/?#/product/sku/(.*)'.format(self.SITE),
                     self.product_page_url.split('?')[0])
        if not m:
            m = re.match('https?://{}/store/(.*?)\?.*/product/sku/(.*)'.format(self.SITE),
                         self.product_page_url)

        if m:
            self.store_id = m.group(1)
            self.product_id = m.group(2)
            return True

    def _pre_scrape(self):
        self._extract_nutrition_data()

    def _extract_page_tree(self):
        for i in range(3):
            try:
                r = self._request(self.product_page_url, log_status_code=True)
                self.page_raw_text = r.text
                self.tree_html = html.fromstring(self.page_raw_text)
                token = re.search('"Token":"(.*?)"', r.content).group(1)

                api_url = self.API_URL.format(self.SITE, self.store_id, self.product_id)
                self.HEADERS['Authorization'] = token

                request = self._request(api_url)
                if request.status_code == 200:
                    self.product_json = request.json()
                    return

            except Exception as e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', str(e))

                self._set_proxy()

    def _extract_nutrition_data(self):
        if self.product_json:
            for _ in range(3):
                try:
                    if self.product_json.get('Id'):
                        headers = self.HEADERS.copy()
                        headers.update({
                            'Accept': 'application/json'
                        })
                        r = self._request(
                            self.NUTRITION_URL.format(
                                self.SITE,
                                self.product_json.get('Id'),
                                self.store_id.replace('/', '')
                            ),
                            headers=headers,
                        )
                        if r.status_code == 200:
                            self.nutrition_html = html.fromstring(r.text)
                            return
                except Exception as e:
                    print '[WARNING] Can\'t get nutrition data: {}'.format(traceback.format_exc())

                    if self.lh:
                        self.lh.add_list_log('errors', 'Error getting nutrition data: {}'.format(str(e)))

    def not_a_product(self):
        if not self.product_json:
            return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self._brand() + ' ' + self.product_json["Name"]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _size(self):
        return re.search('[\d\.,]+', self.product_json["Size"]).group()

    def _uom(self):
        return self.product_json["Size"].split(self._size() + ' ')[1]

    def _sku(self):
        return self.product_json["Sku"]

    def _upc(self):
        return self._sku()

    def _description(self):
        return self.product_json["Description"] if self.product_json["Description"] else None

    def _ingredients(self):
        for label in self.product_json["Labels"]:
            if not label["Description"] or label["Title"] == 'No additional information available for this product':
                continue
            if label['Title'] == 'Ingredients':
                return [x.strip() for x in label["Description"].split(',')]

    def _warnings(self):
        for label in self.product_json["Labels"]:
            if label['Title'] == 'Warnings / Cautions':
                return label['Description']

    def _nutrition_facts(self):
        if self.nutrition_html is not None:
            nutrition_facts = []
            for fact in self.nutrition_html.xpath('.//span[text()]/parent::div'):
                if fact.xpath('./label/text()') and fact.xpath('./span[1]/text()'):
                    nutrition_facts.append('{}: {}'.format(
                        fact.xpath('./label/text()')[0].strip(),
                        fact.xpath('./span[1]/text()')[0].strip()
                    ))
            return nutrition_facts if nutrition_facts else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        for image_info in self.product_json["ImageLinks"]:
            if image_info["Rel"] == "large":
                return [image_info["Uri"]]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price_long = self.product_json["CurrentPrice"]
        price = re.search('([$0-9.]{2,})', price_long)
        return price.group(1) if price else price_long

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0 if self.product_json["InStock"] else 1

    def _in_stores_out_of_stock(self):
        return 0 if self.product_json["InStock"] else 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        return [self.product_json["Category"]]

    def _brand(self):
        return self.product_json["Brand"]

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo" : _title_seo,
        "size" : _size,
        "uom" : _uom,
        "sku" : _sku,
        "upc" : _upc,
        "description" : _description,
        "ingredients" : _ingredients,
        "warnings" : _warnings,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,

        # CONTAINER : SELLERS
        "price" : _price,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
