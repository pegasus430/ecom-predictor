#!/usr/bin/python

import re
from lxml import html
import traceback

from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words


class FairPriceScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = 'Expected URL format is http://www.fairprice.com.sg/webapp/wcs/stores/servlet/ProductDisplay?.*productId=(\d+)'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

    def not_a_product(self):
        page_type = self.tree_html.xpath('//meta[@property="og:type"]/@content')
        if page_type and page_type[0] == 'product':
            return False
        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = re.search(r'id\':\s\'(\d+)\'', self.page_raw_text)
        return product_id.group(1) if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//h1[contains(@class,"name")]/text()')
        return product_name[0] if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        description = self.tree_html.xpath('//div[@class="longDescription"]//text()')
        return self._clean_text(''.join(description)) if description else None

    def _ingredients(self):
        ingredients = self.tree_html.xpath(
            '//span[contains(text(), "INGREDIENTS")]/parent::div/following-sibling::div//p/text()'
        )
        if ingredients:
            return [x.strip() for x in re.split(r',\s*(?![^()]*\))', ingredients[0])]

    def _nutrition_facts(self):
        nutrition_facts = []
        nutrition_facts_html = self.tree_html.xpath(
            '//span[contains(text(), "NUTRITION FACTS")]/parent::div/following-sibling::div//tr[./td]'
        )
        for fact in nutrition_facts_html:
            fact_data = fact.xpath('./td/text()')
            if fact_data and len(fact_data) >= 1:
                nutrition_facts.append(
                    {
                        fact_data[0].strip(): fact_data[1].strip()
                    }
                )
        return nutrition_facts if nutrition_facts else None

    def _bullets(self):
        bullets = self.tree_html.xpath('//ul[@class="nutr_tbl_about"]//li'
                                       '//p[@id="descAttributeValue_1"]/text()')
        if len(bullets) > 0:
            return "\n".join(bullets)

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath(
            '//div[contains(@class,"show_in_desktop")]//img[@class="zoomthumb"]/@data-large-img-url'
        )
        return [i.strip() for i in image_urls if i.strip()]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath('//span[contains(@class, "price")]/text()')
        return price[0].strip() if price else None

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return int(bool(self.tree_html.xpath('//button[contains(@class, "cartProdNotifyBtn")]')))

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        brand = self.tree_html.xpath('//div[contains(@class, "brand_name")]/text()')
        if not brand:
            brand = [guess_brand_from_first_words(self._product_name())]
        return brand[0] if brand else None

    def _categories(self):
        categories = self.tree_html.xpath('//li[@class="prodBread"]/a/text()')
        return [self._clean_text(i) for i in categories] if categories else None

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER: NONE
        "product_id": _product_id,

        # CONTAINER: PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "description": _description,
        "ingredients": _ingredients,
        "bullets": _bullets,

        # CONTAINER: PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER: SELLERS
        "price": _price,
        "site_online": _site_online,
        "in_stores": _in_stores,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER: CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
