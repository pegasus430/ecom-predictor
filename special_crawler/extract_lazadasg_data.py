#!/usr/bin/python

import re
import json
import traceback

from lxml import html
from extract_data import Scraper
from spiders_shared_code.lazada_variants import LazadaVariants


class LazadaSgScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is https://www.lazada.sg/<product-name>"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.lv = LazadaVariants()
        self.product_json = None

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@name="og:type"]/@content')
        if itemtype and itemtype[0].strip() == 'product':
            self._extract_inline_json()
            return False

        return True

    def _extract_inline_json(self):
        data = re.search(r'app.run\((.*?})\);', html.tostring(self.tree_html), re.DOTALL)
        try:
            self.product_json = json.loads(data.group(1))['data']['root']['fields']
        except Exception as e:
            print traceback.format_exc()

            if self.lh:
                self.lh.add_list_log('errors', str(e))

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath("//input[@id='config_id']//@value")
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[@class='pdp-product-title']/text()")
        return self._clean_text(product_name[0]) if product_name else None

    def _description(self):
        desc = self.tree_html.xpath("//div[contains(@class, 'detail-content')]/descendant::text()")
        return self._clean_text(''.join(desc)) if desc else None

    def _ingredients(self):
        for div in self.tree_html.xpath('//div[@class="pdp-product-desc"]/div'):
            if div.xpath('./*[@itemprop="description"]'):
                for elem in div.xpath('.//*'):
                    if 'Ingredients' in elem.text_content():
                        ingredients = re.sub('Ingredients', '', elem.text_content())
                        return [i.strip() for i in ingredients.split(',')]

    def _specs(self):
        specs_list = []
        specs = {}
        feature_block = self.product_json.get('product', {}).get('desc')
        if feature_block:
            feature_block = html.fromstring(feature_block)
            feature_groups = feature_block.xpath('.//p/text()')
            spec_start = False
            for fg in feature_groups:
                if 'Specification:' in fg:
                    spec_start = True
                    continue
                if not self._clean_text(fg):
                    spec_start = False

                if spec_start is True:
                    specs_list.append(fg)

        if specs_list:
            for sp in specs_list:
                spec = sp.split(':')
                specs[spec[0]] = spec[1].strip()

        if not specs:
            spec_groups = self.product_json.get('specifications')
            sku = self._sku()
            for key, spec in spec_groups.items():
                if spec.get('features', {}).get('SKU') == sku:
                    specs = spec.get('features')
                    break

        return specs if specs else None

    def _features(self):
        features = []
        feature_block = self.product_json.get('product', {}).get('desc')
        if feature_block:
            feature_block = html.fromstring(feature_block)
            feature_groups = feature_block.xpath('.//p/text()')
            for fg in feature_groups:
                if 'Features:' in fg:
                    continue
                if 'Specification:' in fg:
                    break
                if self._clean_text(fg):
                    features.append(fg)

        return features if features else None

    def _bullets(self):
        bullets = self.tree_html.xpath("//div[contains(@class, 'pdp-product-highlights')]//li/text()")
        return bullets if bullets else None

    def _variants(self):
        self.lv.setupCH(self.tree_html, self.product_page_url)
        return self.lv._variants()

    ###########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ###########################################

    def _image_urls(self):
        images = self.tree_html.xpath("//div[@class='item-gallery__image-wrapper']//img/@src")
        images = ['https:' + re.sub(r'jpg_(.*).jpg', 'jpg_670x670q75.jpg', image) for image in images]

        return images if images else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//div[@class='pdp-product-price']"
                                     "//span[contains(@class, 'pdp-price_color_orange')]/text()")
        return price[0] if price else None

    def _price_currency(self):
        return "SGD"

    def _temp_price_cut(self):
        return int(bool(self.tree_html.xpath("//span[contains(@class, 'pdp-product-price__discount')]/text()")))

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        out_of_stock = self.tree_html.xpath("//span[@class='prod_stock_number isOutOfStock']")
        if out_of_stock:
            return 1
        return 0

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        self.review_count = self.product_json.get('review', {}).get('ratings', {}).get('rateCount')
        self.average_review = self.product_json.get('review', {}).get('ratings', {}).get('average')
        scores = self.product_json.get('review', {}).get('ratings', {}).get('scores', [])
        review_list = [[5 - i, score] for i, score in enumerate(scores)]

        return review_list if review_list else None

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        brand = self.tree_html.xpath(
            "//div[@class='pdp-product-brand']"
            "//a[contains(@class, 'pdp-product-brand__brand-link')]/text()"
        )
        if brand:
            return brand[0]

        brand = self.product_json.get('product', {}).get('brand', {}).get('name')

        return brand

    def _categories(self):
        categories = self.tree_html.xpath(
            "//li[@class='breadcrumb_item']"
            "//a[@class='breadcrumb_item_anchor']//span/text()"
        )

        return categories if categories else None

    def _sku(self):
        skus = self.product_json.get('productOption', {}).get('skuBase', {}).get('skus', [])
        return skus[0].get('innerSkuId') if skus else None

    def _model(self):
        model = None
        skus = self.product_json.get('productOption', {}).get('skuBase', {}).get('skus', [])
        if skus:
            selected_sku = skus[0].get('skuId')
            features = self.product_json.get('specifications', {}).get(selected_sku)
            if features:
                model = features.get('features', {}).get('Model')

        return model

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "brand": _brand,
        "categories": _categories,
        "product_id": _product_id,
        "sku": _sku,
        "model": _model,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_name,
        "description": _description,
        "ingredients": _ingredients,
        "specs": _specs,
        "features" : _features,
        "bullets" : _bullets,
        "variants": _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "temp_price_cut": _temp_price_cut,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : REVIEWS
        "reviews": _reviews
        }
