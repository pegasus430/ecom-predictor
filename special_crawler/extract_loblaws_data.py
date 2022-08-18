# -*- coding: utf-8 -*-
# !/usr/bin/python

import re
import json
import requests
import traceback
from lxml import html
from extract_data import Scraper

class LoblawsScraper(Scraper):

    STORE_LOCATOR_URL = 'https://www.loblaws.ca/store-locator'
    STORE_SAVE_URL = 'https://www.loblaws.ca/booking/save?CSRFToken={}&cartId={}'
    LOCATION_ID = '1079'

    def not_a_product(self):
        if self.tree_html.xpath('//div[@class="page-product-display product-display-page container"]'):
            return False
        return True

    def _set_target_store(self, session):
        resp = self._request(
            self.STORE_LOCATOR_URL,
            session=session
        )
        if resp.status_code == 200:
            csrf_token = re.search(r'CSRFToken=(.*?)"', resp.text)
            cart_id = re.search(r'cartId=(.*?)"', resp.text)
            if csrf_token and cart_id:
                headers = {
                    'Content-Type':'application/json',
                    'X-Requested-With':'XMLHttpRequest',
                }
                data = {
                    'pickupLocationId': self.LOCATION_ID,
                }
                resp = self._request(
                    self.STORE_SAVE_URL.format(csrf_token.group(1), cart_id.group(1)),
                    data=json.dumps(data),
                    headers=headers,
                    verb='post',
                    session=session
                )
                return True
        return False

    def _extract_page_tree(self):
        for i in range(self.MAX_RETRIES):
            try:
                session = requests.Session()
                if not self._set_target_store(session):
                    continue
                self.ERROR_RESPONSE['failure_type'] = None
                resp = self._request(
                    self.product_page_url,
                    session=session,
                    log_status_code=True
                )
                if resp.status_code != 200:
                    self.ERROR_RESPONSE['failure_type'] = resp.status_code
                    if resp.status_code != 404:
                        continue
                self.page_raw_text = resp.content
                self.tree_html = html.fromstring(self.page_raw_text)
                return
            except Exception as e:
                if self.lh:
                    self.lh.add_list_log('errors', str(e))
                print traceback.format_exc(e)
        self.is_timeout = True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _product_id(self):
        product_id = self.tree_html.xpath('//div[@data-product-id]/@data-product-id')
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath(
            '//div[@class="save-to-list-popup  is-btn-not-animated animation-down dark"]'
            '/@data-product-name'
        )
        return product_name[0] if product_name else None

    def _product_code(self):
        return self._product_name()
 
    def _product_title(self):
        return self._product_name()
 
    def _title_seo(self):
        title_seo = self.tree_html.xpath('//title/text()')
        return title_seo[0] if title_seo else None

    def _description(self):
        description = self.tree_html.xpath('//div[@class="row-product-description row"]/p/text()')
        return description[0] if description else None

    def _ingredients(self):
        ingredients_text_list = self.tree_html.xpath('//div[@class="ingredients-list"]/text()')
        if ingredients_text_list:
            return [x.strip() for x in ingredients_text_list[1].split(',')]

    def _nutrition_facts(self):
        nutrition_facts = []
        nutrition_labels = self.tree_html.xpath(
            '//div[@class="row-nutrition-fact-attr visible-sm row"]'
            '//span[@class="nutrition-label"]/text()'
        )
        nutrition_values = self.tree_html.xpath(
            '//div[@class="row-nutrition-fact-attr visible-sm row"]'
            '//span[@class="nutrition-label"]/following-sibling::text()[1]'
        )
        if nutrition_labels and nutrition_values:
            for k,label in enumerate(nutrition_labels):
                if nutrition_values[k].strip():
                     nutrition_facts.append([label.strip(), nutrition_values[k].strip()])
        if nutrition_facts:
            return nutrition_facts

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _image_urls(self):
        img_raw_urls = self.tree_html.xpath('//div[@class="module-product-thumbnail"]//img/@srcset')
        if img_raw_urls:
            image_urls = []
            for url in img_raw_urls:
                if url not in image_urls:
                    image_urls.append(url)
            return image_urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath('//span[@class="reg-price-text"]/text()')
        return price[0] if price else None

    def _site_online(self):
        return 1

    def _in_stores(self):
        return 1

    def _marketplace(self):
        return 0

    def _site_online_out_of_stock(self):
        if self.tree_html.xpath('//div[@data-product-id="%s"]//span[@class="add-to-cart-text"]' % self._product_id()):
            return 0
        return 1     

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.tree_html.xpath('//ul[@class="bread-crumb pull-left"]//a/text()')
        return [x.strip() for x in categories] if categories else None

    def _brand(self):
        brand = self.tree_html.xpath('//span[@class="product-sub-title"]/text()')
        return brand[0].strip() if brand else None

    ##########################################
    ################ RETURN TYPES
    ##########################################
    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_code": _product_code,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "description": _description,
        "ingredients": _ingredients,
        "nutrition_facts": _nutrition_facts,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "site_online": _site_online,
        "in_stores": _in_stores,
        "marketplace": _marketplace,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
