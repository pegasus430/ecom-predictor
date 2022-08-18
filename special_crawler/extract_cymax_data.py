#!/usr/bin/python

import re
import json
import traceback

from lxml import html
from extract_data import Scraper
from spiders_shared_code.cymax_variants import CymaxVariants


class CymaxScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.cymax.com/<product-name>"

    REVIEW_URL = 'https://www.cymax.com/WebService/WService.svc/Reviews_Get'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.review_json = {}
        self.cv = CymaxVariants()

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')

        if itemtype and itemtype[0].strip() == "product":
            self.cv.setupCH(self.tree_html)
            return False
 
        return True

    def _pre_scrape(self):
        self._fetch_review_json()


    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _fetch_review_json(self):
        try:
            review_json = self._request(self.REVIEW_URL,
                                        verb = 'post',
                                        headers = {'Content-Type': 'application/json'},
                                        data = json.dumps({'productId': self._product_id()})).json()
            self.review_json = json.loads(review_json['d'])
        except Exception as e:
            print traceback.format_exc()

            if self.lh:
                self.lh.add_list_log('errors', 'Error fetching review json: {}'.format(e))

    def _product_id(self):
        product_id = self.tree_html.xpath("//*[@name='Main.ProdID']/@value")
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath("//div[@id='product-title-review']//h1/text()")
        return product_name[0] if product_name else None

    def _description(self):
        description = self.tree_html.xpath("//div[@id='productFeatures']"
                                           "//div[contains(@class, 'user-edited-text')]")
        if description:
            return description[0].text_content().strip()

    def _bullets(self):
        bullets = self.tree_html.xpath(
            '//div[@id="productFeatures"]//ul[preceding::*[contains(text(), "Features")]][1]'
        )
        if bullets:
            return '\n'.join([x.strip() for x in bullets[0].xpath('./li/text()')])

    def _specs(self):
        specs = {}

        found_specs = False

        for elem in self.tree_html.xpath("//div[@id='productFeatures']//div/*"):
            if elem.text_content().strip() == 'Specifications:':
                found_specs = True

            if found_specs and elem.tag == 'ul':
                for spec_option in elem.xpath('./li/text()'):
                    for spec in spec_option.split(';'):
                        if ':' in spec:
                            spec_name, spec_value = spec.split(':')
                            specs[spec_name] = spec_value.strip()
                return specs

    def _sku(self):
        for spec in self.tree_html.xpath("//div[@id='productSpecs']//tr"):
            spec = spec.xpath('./td//text()')
            if len(spec) == 2:
                spec_name, spec_value = spec
                if spec_name == 'SKU:':
                    return spec_value.strip()

    def _no_longer_available(self):
        return 0

    def _variants(self):
        return self.cv._variants()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _image_urls(self):
        image_urls = self.tree_html.xpath("//div[@id='gallery-slider-area']//img/@src-zoom")
        return image_urls if image_urls else None

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################
    def _average_review(self):
        average_review = self.tree_html.xpath("//div[@id='review-resume']//@data-review-value")
        return float(average_review[0]) if average_review else None

    def _review_count(self):
        review_count =re.search('(\d+) reviews', html.tostring(self.tree_html))
        if review_count:
            return int(review_count.group(1))
        return 0

    def _reviews(self):
        if self._review_count():
            review_counts = [0]*5

            for review_value in self.review_json:
                review_counts[int(review_value['OverallRating']) - 1] += 1

            return [[5 - value, count] for value, count in enumerate(review_counts)]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath("//span[@id='product-main-price']/text()")
        return price[0].strip() if price else None

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return int(bool(
            self.tree_html.xpath('//div[contains(@class, "modal")]//p[contains(text(), "out-of-stock")]')
        ))

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.tree_html.xpath("//ol[contains(@class, 'breadcrumb')]//li/a/text()")
        return categories[1:] if categories else None

    def _brand(self):
        brand = self.tree_html.xpath("//div[@id='aboutBrand']//a[contains(@class, 'font-bold')]/text()")
        if brand:
            return brand[0].strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################
    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "description": _description,
        "bullets": _bullets,
        "specs": _specs,
        "sku": _sku,
        "no_longer_available": _no_longer_available,
        "variants" : _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : REVIEWS
        "review_count": _review_count,
        "average_review": _average_review,
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
