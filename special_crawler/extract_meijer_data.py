#!/usr/bin/python

import re
import json
import requests

from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words


class MeijerScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.meijer.com/product/<product-name>"

    STORE_URL = 'https://www.meijer.com/includes/ajax/account_store_data.jsp'

    WEBCOLLAGE_POWER_PAGE = 'https://scontent.webcollage.net/meijer/power-page?ird=true&channel-product-id={}'

    def _extract_page_tree(self):
        with requests.Session() as s:
            self._request(self.STORE_URL, session=s)

            r = self._request(self.product_page_url, session=s, log_status_code=True)

            self.page_raw_text = r.content
            self.tree_html = html.fromstring(self.page_raw_text)

    def check_url_format(self):
        m = re.match("https?://www.meijer.com/product/.*", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        itemtype = self.tree_html.xpath("//div[@class='shopView inline-product-detail']/@itemtype")

        if itemtype and itemtype[0].strip() == "http://schema.org/Product":
            return False

        return True

    def _pre_scrape(self):
        self._extract_webcollage_contents()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return re.findall('\d+', self.product_page_url)[-1]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.tree_html.xpath("//h1[@itemprop='name']/text()")[0]

    def _upc(self):
        upc = self.tree_html.xpath("//input[@name='upc']/@value")
        return upc[0] if upc else None

    def _description(self):
        short_description = self.tree_html.xpath("//div[@itemprop='description']/text()")
        if short_description:
            short_description = self._clean_text(''.join(short_description)).replace('\'', '')
        return short_description

    def _no_longer_available(self):
        return 0

    def _long_description(self):
        features = self.tree_html.xpath('//h3[text()="Features"]/..//span[@class="map-value"]')
        if features:
            return features[0].text_content()

    def _ingredients(self):
        ingredients = []
        ingredient_list = self.tree_html.xpath('//div[@id="product-ingredients"]/p/text()')[0].split(',')
        for ingredient in ingredient_list:
            ingredients.append(self._clean_text(ingredient).replace('.', ''))
        return ingredients

    def _nutrition_facts(self):
        nutriton_facts = []
        nutriton_facts_groups = self.tree_html.xpath(
            '//div[@class="nutri-table-container"]//table[not(@id="nutiTabelHead")]//tbody//tr')

        for nutriton_facts_group in nutriton_facts_groups:
            if len(nutriton_facts_group.xpath('./td')) == 2:
                nutriton_facts.append(': '.join(nutriton_facts_group.xpath('.//td/text()')))

        return nutriton_facts

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        self.protocal = 'https:'
        image_url_list = []
        image_url_info = re.search('altImageObject = (.*?);', html.tostring(self.tree_html), re.DOTALL).group(1)
        html_image_url = self.tree_html.xpath("//ul[@id='wrapper-ul']//li//img/@src")
        main_image = self.tree_html.xpath("//input[@name='imageUrl']/@value")

        if html_image_url:
            for image_url in html_image_url:
                image_url_list.append(self.protocal + image_url.replace('0100', '2000'))
            return image_url_list
        if main_image:
            image_url_list.append(self.protocal + main_image[0].replace('0100', '2000'))
        if image_url_info:
            image_url_info_json = json.loads(image_url_info)
            if image_url_info_json:
                for image_url in image_url_info_json:
                    if '_2000' in image_url:
                        image_url_list.append(self.protocal + image_url.get('_2000'))
        return image_url_list

    def _video_urls(self):
        return self.wc_videos if self.wc_videos else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.tree_html.xpath(
            "//input[@name='salePrice' and @value!='0.0']/@value"
        )
        if not price:
            price = self.tree_html.xpath(
                "//input[@name='price']/@value"
            )
        if price:
            price = re.match(r'\d{1,3}[,\.\d{3}]*\.?\d*', price[0])
        return float(price.group()) if price else None

    def _in_stores(self):
        return 1

    def _site_online(self):
        store = self.tree_html.xpath('//div[@id="qty-stock-block"]//button/text()')
        if store and store[0] == 'Available In-Store Only':
            return 0
        return 1

    def _site_online_out_of_stock(self):
        stock = self.tree_html.xpath('//span[@class="availability-message"]/text()')
        if self._site_online() == 1:
            if stock and 'Currently Out of Stock' in stock[0]:
                return 1
            else:
                return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath(
            "//div[@id='breadcrumb-wrapper']"
            "//ol[@class='breadcrumb hidden-xs']"
            "//li//a/text()")

        return categories[1:] if categories else None

    def _brand(self):
        return guess_brand_from_first_words(self._product_name())

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "upc" : _upc,
        "description": _description,
        "no_longer_available": _no_longer_available,
        "long_description": _long_description,
        "ingredients": _ingredients,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand
        }
