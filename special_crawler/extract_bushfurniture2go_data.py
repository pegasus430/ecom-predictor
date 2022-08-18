#!/usr/bin/python

import re
from lxml import html

from extract_data import Scraper
from spiders_shared_code.bushfurniture2go_variants import Bushfurniture2goVariants


class Bushfurniture2goScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.bv = Bushfurniture2goVariants()

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def not_a_product(self):
        self.bv.setupCH(self.tree_html)
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = re.search(r'var wcCpi = "(.*?)";', self.page_raw_text)
        return product_id.group(1) if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//div[@class="product-name"]//h1/text()')
        return product_name[0] if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        title_seo = self.tree_html.xpath('//title/text()')
        return title_seo[0] if title_seo else None

    def _sku(self):
        model = self.tree_html.xpath('//div[@class="sku"]//span[@itemprop="sku"]/text()')
        return model[0] if model else None

    def _features(self):
        features = None
        feature_box = self._get_block('Features')

        if feature_box:
            features = feature_box.xpath('.//span[contains(@class, "full-description")]//ul//li/text()')

        return features if features else None

    def _description(self):
        desc = None
        desc_box = self._get_block('Description')

        if desc_box:
            desc = desc_box.xpath('.//span[contains(@class, "full-description")]/descendant::text()')

        return self._clean_text(''.join(desc)) if desc else None

    def _long_description(self):
        long_desc = None
        feature_box = self._get_block('Features')

        if feature_box:
            titles = feature_box.xpath('.//h2')
            for title in titles:
                if 'Product Details' in title.xpath('./text()'):
                    long_desc = title.xpath('./following-sibling::p[1]/descendant::text()')
                    break

        return self._clean_text(''.join(long_desc)) if long_desc else None

    def _variants(self):
        return self.bv._variants()

    def _get_block(self, block_name):
        block = None
        prod_boxes = self.tree_html.xpath('//ul[@id="prodBoxes"]//li')
        for prod_box in prod_boxes:
            if block_name in prod_box.xpath('.//a//span/text()'):
                block = prod_box
                break

        return block

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//div[@class="picture-thumbs"]//img/@src')
        return image_urls if image_urls else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _site_online(self):
        return 1

    def _in_stores(self):
        return 0

    def _marketplace(self):
        return 0

    def _site_online_out_of_stock(self):
        return 0

    def _price(self):
        price = self.tree_html.xpath(
            '//div[contains(@class, "pdp-product-info")]'
            '//div[@class="product-price"]//span/text()'
        )

        return price[0] if price else None

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath('//div[@class="breadcrumb"]//li//a//span/text()')
        return categories[1:] if categories else None

    def _brand(self):
        brand = self.tree_html.xpath(
            '//span[contains(@class, "full-description")]'
            '//a[contains(@href, "byBrand")]/text()'
        )
        return brand[0] if brand else None

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "sku": _sku,
        "features": _features,
        "description": _description,
        "long_description": _long_description,
        "variants": _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "site_online": _site_online,
        "in_stores": _in_stores,
        "marketplace": _marketplace,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "price": _price,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
