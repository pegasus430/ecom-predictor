#!/usr/bin/python

import re
import json
from lxml import html

from extract_data import Scraper
from spiders_shared_code.dockers_variants import DockersVariants


class DockersScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    REVIEW_URL = 'https://api.bazaarvoice.com/data/batch.json?passkey=casXO49OnnLONGhfxN6TSfvEmsGWbyrfjtFtLGZWnBUeE' \
                 '&apiversion=5.5&displaycode=18029-en_us&resource.q0=products&filter.q0=id' \
                 '%3Aeq%3A{0}&stats.q0=questions%2Creviews'

    VARIANTS_DATA_URL = "https://www.dockers.com/{locale}/en_{locale}/p/{prod_id}/data"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = None
        self.variants_data = {}
        self.buy_stack_json = None

        self.dk = DockersVariants()

        self._set_proxy()

    def not_a_product(self):
        if self._no_longer_available():
            return False

        not_a_product = True
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')

        if itemtype and itemtype[0].strip() == 'product':
            not_a_product = False

        product_infos = self.tree_html.xpath('//script[@type="application/ld+json"]/text()')
        if len(product_infos) == 2 and '"@type":"Product"' in product_infos[1]:
            not_a_product = False

        if not not_a_product:
            self.dk.setupCH(self.tree_html)
            self.product_json = self.dk._extract_product_json()
            self._get_variants_data()

        return not_a_product

    def _get_locale(self):
        locale = re.search(r'dockers.com/([A-Z]{2})/', self.product_page_url)
        return locale.group(1) if locale else 'US'

    def _get_variants_data(self):
        if self._get_locale() and self._product_id():
            resp = self._request(self.VARIANTS_DATA_URL.format(locale=self._get_locale(), prod_id=self._product_id()))
            if resp.status_code == 200:
                self.variants_data = json.loads(resp.text)

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.product_json.get('product', {}).get('code')
        if not product_id:
            product_id = re.search(r'/p/(\d+)', self.product_page_url)
            product_id = product_id.group(1) if product_id else None

        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        name = self.tree_html.xpath('//div[contains(@class, "page-title")]//h1[@itemprop="name"]/text()')
        return name[0] if name else None

    def _description(self):
        return self.product_json.get('product', {}).get('description')

    def _variants(self):
        return self.dk._variants(self.variants_data)

    def _no_longer_available(self):
        if "this product is no longer available" in html.tostring(self.tree_html):
            return 1

        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        images = self.tree_html.xpath('//div[contains(@class, "carousel")]//picture//img//@data-src')

        return [i.split('?')[0] for i in images]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price_info = self.product_json.get('product', {}).get('price', {})
        price_amount = price_info.get('softPrice')
        if not price_amount:
            price_amount = price_info.get('hardPrice')
        if not price_amount:
            price_amount = price_info.get('regularPrice')

        return float(price_amount) if price_amount else None

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return int(
            bool(self.tree_html.xpath(
                '//button[contains(@class, "outOfStock")]'
            ))
        )

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        return 'Dockers'

    def _categories(self):
        categories = self.tree_html.xpath('//li[contains(@class, "breadcrumb")]/a/text()')
        return categories if categories else None

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_name,
        "title_seo": _product_name,
        "description": _description,
        "variants": _variants,
        "no_longer_available": _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "brand": _brand,
        "categories": _categories
        }
