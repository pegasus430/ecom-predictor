#!/usr/bin/python

import re
import json
import traceback
import urlparse
from urllib import urlencode

from lxml import html
from extract_data import Scraper, deep_search
from spiders_shared_code.cvs_variants import CvsVariants


class CVSScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    API_URL = 'https://cvshealth-cors.groupbycloud.com/api/v1/search'

    DATA = {'collection': 'productsLeaf',
            'fields': ['*'],
            'refinements': [{'exclude': False,
                             'navigationName': 'id',
                             'type': 'Value',
                             'value': None}]}

    INVALID_URL_MESSAGE = 'Expected URL format is http(s)://(www.)cvs.com/shop/*'

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
                 "passkey=ll0p381luv8c3ler72m8irrwo" \
                 "&apiversion=5.5" \
                 "&displaycode=3006-en_us" \
                 "&resource.q0=products" \
                 "&filter.q0=id:eq:{}" \
                 "&stats.q0=reviews"

    WEBCOLLAGE_POWER_PAGE = "https://scontent.webcollage.net/cvs/power-page?ird=true&channel-product-id={}"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = {}
        self.selected_variant = {}

        self.cv = CvsVariants()

    def _fix_url(self):
        if 'skuId=' not in self.product_page_url:
            params = {'skuId': self._product_id()}
            url_parts = list(urlparse.urlparse(self.product_page_url))
            query = dict(urlparse.parse_qsl(url_parts[4]))
            query.update(params)
            url_parts[4] = urlencode(query)
            self.product_page_url = urlparse.urlunparse(url_parts)

    def check_url_format(self):
        m = re.match("https?://(www.)?cvs.com/shop/.*", self.product_page_url)
        self._fix_url()
        return bool(m)

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def _pre_scrape(self):
        self._get_product_json()
        self.cv.setupCH(self.product_json, self._sku())
        for variant in self.product_json['variants']:
            for subvariant in variant['subVariant']:
                if subvariant['p_Sku_ID'] == self._sku():
                    self.selected_variant = subvariant
                    break
        self._extract_webcollage_contents(product_id=self._sku())

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _get_product_json(self):
        try:
            self.DATA['refinements'][0]['value'] = self._product_id()
            r = self._request(self.API_URL, data = json.dumps(self.DATA), verb='post')
            self.product_json = deep_search('allMeta', r.json())[0]
        except Exception as e:
            print traceback.format_exc()

            if self.lh:
                self.lh.add_list_log('errors', str(e))

    def _product_id(self):
        return re.search('prodid-(\d+)', self.product_page_url).group(1)

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return deep_search('title', self.product_json)[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _sku(self):
        return re.search('skuid=(\d+)', self.product_page_url, re.I).group(1)

    def _item_num(self):
        return self._sku()

    def _description(self):
        description = self.selected_variant.get('p_Product_Details')
        if description:
            return self._remove_tags(description)

    def _directions(self):
        directions = self.selected_variant.get('p_Product_Directions')
        if directions:
            return self._remove_tags(directions)

    def _ingredients(self):
        ingredients = self.selected_variant.get('p_Product_Ingredients')
        if ingredients:
            return [i.strip() for i in ingredients.split(',')]

    def _warnings(self):
        warnings = self.selected_variant.get('p_Product_Warnings')
        if warnings:
            return self._remove_tags(warnings)

    def _variants(self):
        return self.cv._variants()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        IMG_BASE = 'https://www.cvs.com/bizcontent/merchandising/productimages/large/'
        return [IMG_BASE + i for i in self.selected_variant['upc_image']]

    def _video_urls(self):
        return self.wc_videos if self.wc_videos else None

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _review_id(self):
        return self._sku()

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        return float(self.selected_variant['gbi_Actual_Price'])

    def _in_stores(self):
        return 1

    def _marketplace(self):
        return 0

    def _site_online(self):
        if self.selected_variant.get('retail_only') == '1':
            return 0
        return 1

    def _site_online_out_of_stock(self):
        if self._site_online():
            if self.selected_variant['p_Product_Availability'].endswith('1'):
                return 1
            return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        return deep_search('categories', self.product_json)[0][0].values()

    def _brand(self):
        return self.selected_variant.get('ProductBrand_Brand')

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _remove_tags(self, html_string):
        html_string = re.sub('<li>|<br/>', '\n', html_string)
        html_string = re.sub('<[^>]*?>', '', html_string)
        return html_string

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
        "item_num": _item_num,
        "sku": _sku,
        "description": _description,
        "directions": _directions,
        "ingredients": _ingredients,
        "warnings": _warnings,
        "variants": _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "marketplace": _marketplace,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
