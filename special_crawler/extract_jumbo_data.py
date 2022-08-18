# -*- coding: utf-8 -*-
#!/usr/bin/python

import re
import requests
import traceback
from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words

class JumboScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.jumbo.com(:80)/.*"

    HOME_URL = 'https://www.jumbo.com/'

    STORE_SEARCH_URL = 'https://www.jumbo.com/INTERSHOP/rest/WFS/Jumbo-Grocery-Site' \
                       '/webapi/stores?address={zip_code}'

    STORE_PICK_URL = 'https://www.jumbo.com/INTERSHOP/rest/WFS/Jumbo-Grocery-Site/' \
                     'webapi/stores/{pick_id}'

    HEADERS = {'accept': None} # for some reason jumbo doesn't like accept: text/html

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.zip_code = kwargs.get('zip_code') or '1011'

        self._set_proxy()

    def _extract_page_tree(self):
        for i in range(3):
            try:
                # Use 'with' to ensure the session context is closed after use.
                with requests.Session() as s:
                    # Get homepage to establish session
                    self._request(self.HOME_URL, session=s)

                    # Set auth cookies
                    store_search_url = self.STORE_SEARCH_URL.format(zip_code=self.zip_code)
                    stores = self._request(store_search_url, session=s).content

                    uuid = re.findall('"uuid":(.*?),', stores, re.DOTALL)
                    store_pick_url = self.STORE_PICK_URL.format(pick_id=uuid[0])

                    self._request(store_pick_url, session=s)

                    # An authorised request.
                    response = self._request(self.product_page_url, session=s, log_status_code=True)

                    if response.ok:
                        content = response.text
                        self.tree_html = html.fromstring(content)
                        return
                    else:
                        self.ERROR_RESPONSE['failure_type'] = response.status_code
            except:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', str(e))
 
        self.is_timeout = True # return failure

    def check_url_format(self):
        m = re.match(r"^https?://www.jumbo.com(:80)?/.*$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[contains(@class, "jum-product-image-group")]')) < 1:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = re.search(r'\"id\":\"(.*?)\",', html.tostring(self.tree_html), re.DOTALL)
        if not product_id:
            product_id = re.search(r'/([A-Z0-9]+)/?', self.product_page_url)
        if product_id:
            return product_id.group(1)

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//h1[@data-dynamic-block-name]/text()')
        if product_name:
            return product_name[0]

    def _description(self):
        description = ''
        description_elements = self.tree_html.xpath('//section[contains(@class, "jum-summary-info")]'
                                                    '/div[contains(@class, "jum-summary-description")]'
                                                    '//text()')
        if description_elements:
            for desc in description_elements:
                if desc == '\n':
                    pass
                else:
                    description += desc

        return description.strip() if description else None

    def _manufacturer(self):
        manufacturer = self.tree_html.xpath('//div[contains(@class, "jum-product-brand-info")]'
                                            '/p/a[contains(@target, "_new")]//text()')
        if manufacturer:
            return manufacturer[0]

    def _ingredients(self):
        ingredients = self.tree_html.xpath('//div[contains(@class, "jum-ingredients-info")]/ul/li')
        if ingredients:
            return [i.text_content() for i in ingredients]

    def _warnings(self):
        warnings = self.tree_html.xpath("//div[contains(@class, 'jum-product-allergy-info')]//ul//li/text()")
        return warnings[0] if warnings else None

    def _nutrition_facts(self):
        nutrition_facts = []
        nutrition_names = self.tree_html.xpath("//div[contains(@class, 'jum-nutritional-info')]//tbody//tr")
        nutrition_values = self.tree_html.xpath("//div[contains(@class, 'jum-nutritional-info')]//tbody//tr")
        for data in nutrition_values:
            name = nutrition_names[nutrition_values.index(data)].xpath('.//th/text()')
            value = ','.join(data.xpath(".//td/text()"))
            if not name:
                nutrition_facts.append(value)
            else:
                nutrition_facts.append(' '.join([name[0], value]))
        if nutrition_facts:
            return nutrition_facts

    def _long_description(self):
        description = self.tree_html.xpath('//section[contains(@class, "jum-additional-info")]'
                                           '/div[contains(@class, "jum-nutritional-info")]'
                                           '//text()')
        if description and len(description) > 1:
            return description[2].strip()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_list = []
        image_urls = self.tree_html.xpath('//div[contains(@class, "jum-product-images")]'
                                          '//img/@data-jum-hr-src')
        if image_urls:
            for image_url in image_urls:
                image_url = image_url.replace('90x90', '360x360')
                image_list.append(image_url)
            return image_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.tree_html.xpath('//div[@class="jum-item-price"]//input[@jum-data-price]/@jum-data-price')
        if price:
            return round(float(price[0]), 2)

    def _price_currency(self):
        return 'EUR'

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return int(not bool(self.tree_html.xpath('//button[contains(@id,"addToCart")]')))

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        return self.tree_html.xpath('//nav[contains(@class, "jum-breadcrumb")]/ol/li/a//text()')

    def _brand(self):
        brand = self.tree_html.xpath('//div[contains(@class, "jum-product-info-group")]'
                                     '/div[contains(@class, "jum-add-product")]/@data-jum-brand')
        if brand:
            return brand[0]
        else:
            return guess_brand_from_first_words(self._product_title())

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "description": _description,
        "long_description": _long_description,
        "manufacturer": _manufacturer,
        "ingredients": _ingredients,
        "warnings": _warnings,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "price_currency": _price_currency,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
