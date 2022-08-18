#!/usr/bin/python

import re

from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words
from lxml import html
from HTMLParser import HTMLParser

class CoopScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.coop.nl/.*"

    NUTRIENTS_PAGE_URL = 'https://widgets.syndy.com/widgets/nutrients/{product_id}' \
                         '/nl?key=62edbcd9daab4fd48b16deca22950cb6'

    def check_url_format(self):
        m = re.match(r"^https?://www.coop.nl/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[@class="container"]')) < 1:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.product_page_url.split('/')[-1]

        return product_id if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _brand(self):
        return guess_brand_from_first_words(self._product_name())

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[@itemprop='name']//text()")
        return product_name[0] if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _sku(self):
        return self._product_id()

    def _description(self):
        description = self.tree_html.xpath('//dl[@class="definitionList"]/dd//p//text()')
        return self._clean_text(''.join(description)) if description else None

    def _nutrition_fact_count(self):
        product_id = self.tree_html.xpath('//div[@class="syndy-nutrients"]/@data-syndy-productid')
        nutrition_fact_count = 0

        if product_id:
            nutrition_page_url = self.NUTRIENTS_PAGE_URL.format(product_id=product_id[0])
            headers = {
                'X-Widget-Type': 'jssdk-nutrients',
                'X-Widget-Referrer': self.product_page_url
            }
            nutrition_page = self._request(nutrition_page_url, headers=headers)

            if nutrition_page.ok:
                nutritions = nutrition_page.json().get('Nutrients', {}).get('Records')
                if nutritions:
                    for nutrition in nutritions:
                        if nutrition.get('DefaultAmount') > 0:
                            nutrition_fact_count += 1
                    return nutrition_fact_count

    def _ingredients(self):
        ingredients = self.tree_html.xpath('//div[@class="allergyInfo"]/h3[1]/following-sibling::text()')
        ingredient_list = []
        for ing in ingredients[0].split(','):
            ingredient_list.append(ing.strip())
        if 'Ingredi' in html.tostring(self.tree_html):
            return ingredient_list
        return None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath("//meta[@property='og:image']//@content")
        return image_urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        dollar = self.tree_html.xpath('//ins[@class="price"]/text()')
        cent = self.tree_html.xpath('//ins[@class="price"]/span[@class="sup"]/text()')
        price = HTMLParser().unescape('&euro;') + dollar[0].replace(',', '') + '.' + cent[0]
        return price

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
        categories = None
        categories_info = self.tree_html.xpath('//div[@class="crumbs cf"]/ol/li//span[@itemprop="title"]/text()')
        if categories_info:
            categories = [self._clean_text(ct) for ct in categories_info if self._clean_text(ct)]
        return categories[:-1]

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\r\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "brand": _brand,
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "sku": _sku,
        "description": _description,
        "ingredients": _ingredients,
        "nutrition_fact_count": _nutrition_fact_count,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "price_currency": _price_currency,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        }
