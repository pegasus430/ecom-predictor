#!/usr/bin/python

import re
import time
import json
from lxml import html
import requests
import datetime
import urllib
import random

from extract_data import Scraper


class DollarGeneralScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    WEBCOLLAGE_POWER_PAGE = "https://scontent.webcollage.net/dollargeneral-rwd/power-page?ird=true&channel-product-id={}"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.product_page_url = re.sub('http://', 'https://', self.product_page_url)

    def _pre_scrape(self):
        self._extract_webcollage_contents()

    def _extract_page_tree(self):
        with requests.Session() as session:
            for _ in range(self.MAX_RETRIES):
                domain = re.search(r'(https?://.*?)/', self.product_page_url).group(1)
                response = self._request(
                    self.product_page_url,
                    session=session
                )
                if response.status_code != 200:
                    continue
        
                if 'meta property="og:type"' in response.text:
                    self.page_raw_text = response.text
                    self.tree_html = html.fromstring(response.text)
                    return
        
                if 'Request unsuccessful.' in response.text:
                    self._request(
                        domain + '/_Incapsula_Resource?SWKMTFSR=1&e={}'.format(random.random()),
                        headers = {'Referer': response.url},
                        session = session
                    )
        
                if 'src="/_Incapsula_Resource' in response.text:
                    coded_data = re.search(r'var b=\"(.*?)\";', response.text)
                    if coded_data:
                        data = ''
                        coded_data = coded_data.group(1)
                        for k in range(0, len(coded_data), 2):
                            data += unichr(int(coded_data[k:k+2], 16)) 
                        urls = re.findall(r'(_Incapsula_Resource.*?)\"', data)
                        if urls:
                            timing = []
                            start = self._now_in_seconds()
                            timing.append('s:{}'.format(self._now_in_seconds() - start))
                            self._request(
                                domain+'/'+urls[1],
                                session = session
                            )
                            timing.append('c:{}'.format(self._now_in_seconds() - start))
                            time.sleep(0.5)
                            timing.append('r:{}'.format(self._now_in_seconds() - start))
                            self._request(
                                domain+'/'+urls[2]+urllib.quote('complete ({})'.format(",".join(timing))),
                                session = session
                            )

    def _now_in_seconds(self):
        return (datetime.datetime.now() - datetime.datetime(1970, 1, 1)).total_seconds()

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')
        if itemtype and itemtype[0].strip() == "og:product":
            return False
        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self._sku()

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.tree_html.xpath("//meta[@property='og:title']/@content")[0].strip()

    def parse_description(self):
        description = ''
        desc_list = self.tree_html.xpath('//div[@class="product attribute description"]//text()')
        for desc in desc_list:
            description += self._clean_text(desc)
        return description

    def _description(self):
        description = self.parse_description()
        if 'Ingredients' in description:
            description = re.search('(.*?)Ingredients', description, re.DOTALL).group(1)
        return description

    def _ingredients(self):
        ingredients = []
        description = self.parse_description()
        if 'Ingredients' in description:
            if 'Warnings' in description:
                ingredient_list = re.search('Ingredients(.*?)Warnings', description, re.DOTALL).group(1).split(',')
            else:
                ingredient_list = re.search('Ingredients(.*)', description, re.DOTALL).group(1).split(',')
            for ingredient in ingredient_list:
                if '(' in ingredient and ')' in ingredient:
                    ingredients.append(re.sub('[\.\[\]]', '', ingredient).strip())
                else:
                    ingredients.append(re.sub('[\.\[\]\(\)]', '', ingredient).strip())
            return ingredients

    def _no_longer_available(self):
        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []
        contents = html.tostring(self.tree_html)
        try:
            image_info = self._find_between(contents, '"data": ', '"options"').strip()[:-1]
            image_info = json.loads(image_info)
        except:
            image_info = None

        for image in image_info:
            image_urls.append(image["full"])

        return image_urls

    def _video_urls(self):
        return self.wc_videos if self.wc_videos else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price_info = self.tree_html.xpath("//span[@class='price']/text()")

        if price_info:
            price = price_info[0]
            if not '$' in price:
                price = '$' + price
            return price

    def _in_stores(self):
        return 1

    def _site_online(self):
        available_info = self.tree_html.xpath("//div[@class='available-instore']/text()")

        if available_info and 'available in store' in available_info[0].lower():
            return 0

        return 1

    def _site_online_out_of_stock(self):
        if self._site_online():
            stock_info = self.tree_html.xpath(
                "//div[@class='product-info-stock-sku']"
                "//div[@title='Availability']"
                "//span/text()"
            )

            if stock_info and 'out of stock' in stock_info[0].lower():
                return 1

            return 0

    def _in_stock(self):
        if self._site_online():
            return self._site_online_in_stock()

        return 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories_list = self.tree_html.xpath(
            "//div[contains(@class, 'breadcrumbs')]"
            "//a/text()"
        )
        categories = map(self._clean_text, categories_list)
        if len(categories) > 1:
            return categories[1:]

    def _brand(self):
        brand = self.tree_html.xpath(
            "//div[@id='additional']//td[@data-th='Brand']/text()"
        )
        if brand:
            brand = self._clean_text(brand[0])

        return brand

    def _sku(self):
        sku = self.tree_html.xpath("//div[@itemprop='sku']/text()")

        return sku[0] if sku else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "description" : _description,
        "ingredients" : _ingredients,
        "sku" : _sku,
        "no_longer_available" : _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "price" : _price,
        "in_stores" : _in_stores,
        "site_online" : _site_online,
        "site_online_out_of_stock" : _site_online_out_of_stock,
        "in_stock" : _in_stock,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
