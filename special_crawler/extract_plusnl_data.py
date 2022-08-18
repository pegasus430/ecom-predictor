#!/usr/bin/python

import re
import json
import urlparse
import traceback

from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words


class PlusnlScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.nutrition_json = []

    def not_a_product(self):
        self._extract_nutrition_json()
        return False

    def _extract_nutrition_json(self):
        try:
            json_data = re.search("prodNutritionData = '(.*?)\';", html.tostring(self.tree_html))
            if json_data:
                self.nutrition_json = json.loads(self._clean_text(json_data.group(1)).replace('n{', '{').strip())
        except:
            print traceback.format_exc()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath("//input[@name='ProductSKU']/@value")
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[contains(@class,'Title')]/text()")
        return product_name[0] if product_name else None

    def _description(self):
        short_description = self.tree_html.xpath("//div[contains(@class,'pdpShortDescription')]/text() | "
                                                 "//div[contains(@class,'wettelijke_naam')]//div[@class='prod-attrib-val']/text()")
        return ''.join(short_description) if short_description else None

    def _nutrition_facts(self):
        nutrition_list = []
        nutrition_data = self.nutrition_json
        for data in nutrition_data:
            nutrition_title = data.get('omschrijving')
            nutrition_value = data.get('inhoud')
            nutrition_list.append(nutrition_title + ':' + nutrition_value)

        return nutrition_list if nutrition_list else None

    def _ingredients(self):
        ingredients = self.tree_html.xpath(
            "//div[contains(@class, 'ingredienten')]//div[@class='prod-attrib-val']/b/text() | "
            "//div[contains(@class, 'ingredienten')]//div[@class='prod-attrib-val']/text()"
        )

        return ''.join(ingredients).split(',') if ingredients else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_url_list = []
        image_urls = self.tree_html.xpath("//div[contains(@class, 'kor-product-photo')]//img/@data-src")
        if image_urls:
            for image_url in image_urls:
                image_url_list.append(urlparse.urljoin(self.product_page_url, image_url))
        return image_url_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        sale_price = self.tree_html.xpath('//div[contains(@class,"shape-tekst")]')
        if sale_price:
            price_list = re.findall('\d+', html.tostring(sale_price[0]))
            if len(price_list) > 3:
                return float(price_list[-2] + "." + price_list[-1])
        price = self.tree_html.xpath("//div[@id='prod-detail-ctnr']/@data-price")
        return float(price[0]) if price else None

    def _price_currency(self):
        return 'EUR'

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//ol[@class='ish-breadcrumbs-list']//li//a/text()")
        return categories[1:] if categories else None

    def _brand(self):
        title = self._product_title()
        brand = self.tree_html.xpath("//div[@id='prod-detail-ctnr']/@data-brand")
        if brand:
            brand = brand[0]
        elif title:
            brand = guess_brand_from_first_words(title)
        return brand if brand else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\r\n\t/\\\\]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "description": _description,
        "ingredients": _ingredients,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "price_currency": _price_currency,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand
        }
