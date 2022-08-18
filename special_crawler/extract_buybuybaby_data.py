#!/usr/bin/python

import re
from extract_data import Scraper
import json

class BuyBuyBabyScraper(Scraper):

    INVALID_URL_MESSAGE = "Expected URL format is https://www.buybuybaby.com/store/product/.*"

    REVIEW_URL = "https://buybuybaby.ugc.bazaarvoice.com/8658-en_us/{}/reviews.djs?format=embeddedhtml"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.product_json = {}

    def _pre_scrape(self):
        self._get_product_json()

    def check_url_format(self):
        m = re.match(r"https?://www.buybuybaby.com/store/product/.*", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if self.tree_html.xpath('//div[@id="prodFormContainer"]') < 1:
            return True
        return False

    def _get_product_json(self):
        raw_json_data = self.tree_html.xpath('//input[@id="staticTealiumData"]/@value')
        if raw_json_data:
            self.product_json = json.loads(raw_json_data[0])

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _product_id(self):
        product_id = self.product_json.get('product_id')
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.product_json.get('product_name')
        return product_name[0] if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        title_seo = self.tree_html.xpath('//title/text()')
        return title_seo[0] if title_seo else None

    def _features(self):
        feature_items = self.tree_html.xpath('//div[@id="productInfoWrapper"]//li/text()')
        return feature_items if feature_items else None

    def _description(self):
        description = self.tree_html.xpath('//div[@itemprop="description"]/text()')
        return description[0] if description else None

    def _sku(self):
        sku = self.tree_html.xpath('//p[@class="smalltext prodSKU"]/text()')
        return sku[0].split(' ')[-1] if sku else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _image_urls(self):
        raw_image_urls = re.findall(r'(//s7d1.scene7.com/is/image/BedBathandBeyond/[^"]*?)\?', self.page_raw_text)
        if raw_image_urls:
            image_urls = []
            for img_url in raw_image_urls:
                if img_url not in image_urls:
                    image_urls.append(img_url)
            return ['https:' + str(x) for x in image_urls]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.product_json.get('product_price')
        return price[0] if price else None
    
    def _site_online(self):
        return 1

    def _in_stores(self):
        return 0

    def _marketplace(self):
        return 0

    def _site_online_out_of_stock(self):
        stock_data = self.tree_html.xpath('//link[@itemprop="availability"]/@href')
        if stock_data and ('InStock' in stock_data[0]):
            return 0
        return 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.product_json.get('page_breadcrumb')
        if categories:
            return [x.strip() for x in categories.split('>')[1:-1]]
        
    def _brand(self):
        brand = self.product_json.get('brand_name')
        return brand if brand else None

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo": _title_seo,
        "features": _features,
        "description": _description,
        'sku': _sku,

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