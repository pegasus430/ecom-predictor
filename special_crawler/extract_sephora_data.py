# -*- coding: utf-8 -*-
#!/usr/bin/python

import re
import json
import requests
import urlparse

from lxml import html
from extract_data import Scraper
from spiders_shared_code.sephora_variants import SephoraVariants


class SephoraScraper(Scraper):

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://sephora.com/product/<product-name>"

    REVIEW_URL = "https://api.bazaarvoice.com/data/reviews.json?Filter=ProductId%3A{}&" \
                 "Sort=Helpfulness%3Adesc&Limit=30&Offset=0&Include=Products%2CComments&Stats=Reviews&" \
                 "passkey=rwbw526r2e7spptqd2qzbkp7&apiversion=5.4"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = None
        self.sv = SephoraVariants()

    def check_url_format(self):
        m = re.match(r"^https?://www.sephora.com/product/.*?", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        self.extract_product_json()

        if not self.product_json:
            return True
        self.sv.setupCH(self.product_json)

        return False

    def extract_product_json(self):
        try:
            product_json = self.tree_html.xpath('//script[@id="linkJSON"]/text()')
            product_json = json.loads(product_json[0])
            self.all_json = product_json
            for datum in product_json:
                if 'currentProduct' in datum.get('props', {}):
                    self.product_json = datum.get('props', {}).get('currentProduct', {})
        except:
            self.product_json = None

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _clean_text(text):
        return re.sub("[\n\t\r]", "", text).strip()

    def _product_id(self):
        return self.product_json.get('productId')

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _sku(self):
        return self.product_json.get('currentSku', {}).get('skuId')

    def _product_name(self):
        return self.product_json.get('displayName')

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _description(self):
        return self.product_json.get('longDescription')

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []
        data = self.product_json.get('currentSku', {})
        image_urls.append(urlparse.urljoin(self.product_page_url, data.get('skuImages', {}).get('image50')))
        alt_images = data.get('alternateImages')
        if alt_images:
            for image in alt_images:
                image_urls.append(urlparse.urljoin(self.product_page_url, image.get('image50')))
        return image_urls

    def _video_urls(self):
        video_url = 'https://player.ooyala.com/player/all/{}.m3u8?' \
                    'targetBitrate=2000&ssl=true'
        video_ids = re.findall('videoUrl":"(.*?)"', html.tostring(self.tree_html))
        video_urls = []
        for video in video_ids:
            video_urls.append(video_url.format(video))
        return list(set(video_urls))

    def _variants(self):
        return self.sv._variants()

    def _ingredients(self):
        list = self.tree_html.xpath('//div[@data-comp="Info"]/button')
        for i in range(len(list)):
            content = list[i].xpath('./div/text()')
            if 'ingredients' in content[0].lower():
                break
        array = self.tree_html.xpath('//div[@class="css-17rkxae"]/div')
        array = array[i].xpath('./div[@class="css-1e532l3"]//text()')
        ingredients = ''
        for a in array:
            a = a.encode('utf8').strip()
            if a and '-' not in a[:1]:
                ingredients += a
        ingredient_list = []
        for ingredient in ingredients.split(','):
            ingredient_list.append(ingredient.replace('.', '').strip())
        return ingredient_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        return self.product_json.get('currentSku', {}).get('listPrice')

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        site_online_in_stock = self.product_json.get('apiConfigurationData').get('isInstorePurchaseEnabled')
        if site_online_in_stock:
            return 0
        return 1

    def _in_stores(self):
        in_stores = self.product_json.get('currentSku').get('isFindInStore')
        if in_stores:
            return 1
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.product_json.get('breadcrumbsSeoJsonLd')
        categories = re.findall('"name\\\":\\\"(.*?)\\\"', categories)
        return categories

    def _brand(self):
        return self.product_json.get('brand', {}).get('displayName')

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "sku" : _sku,
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo" : _title_seo,
        "description" : _description,
        "ingredients" : _ingredients,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "video_urls": _video_urls,
        "variants" : _variants,

        # CONTAINER : SELLERS
        "price" : _price,
        "site_online" : _site_online,
        "site_online_out_of_stock" : _site_online_out_of_stock,
        "in_stores" : _in_stores,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
