#!/usr/bin/python

import re
from lxml import html
from extract_data import Scraper

from spiders_shared_code.modcloth_variants import ModClothVariants


class ModClothScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.modcloth.com/.*"

    REVIEW_URL = 'https://readservices-b2c.powerreviews.com/m/368703/l/en_US/product/{}/reviews?'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.mv = ModClothVariants()
        self.is_variants_checked = False
        self.variants = None

    def check_url_format(self):
        m = re.match(r"^http(s)://www.modcloth.com/.*$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[contains(@id, "product-content")]')) < 1:
            return True

        self.mv.setupCH(self.tree_html)
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _extract_auth_key(self):
        auth_pwr = re.findall(r'"POWERREVIEWS_API_KEY":"(.*?)"', html.tostring(self.tree_html))
        if auth_pwr:
            return auth_pwr[0]

    def _product_id(self):
        product_id = re.search('configData.productId = "(\d+)";', html.tostring(self.tree_html), re.DOTALL)
        if not product_id:
            product_id = re.search('/(\d+)', self.product_page_url)
        return product_id.group(1) if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//h1[contains(@class, "product-name")]'
                                            '/text()')
        if product_name:
            return product_name[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        short_description = self.tree_html.xpath('//div[contains(@class, "product-info")]'
                                                 '//div[contains(@class, "tab-content")]'
                                                 '/p/text()')
        if short_description:
            return short_description[0]

    def _variants(self):
        if self.is_variants_checked:
            return self.variants

        self.is_variants_checked = True

        self.variants = self.mv._variants()

        return self.variants

    def _no_longer_available(self):
        arr = self.tree_html.xpath('//div[@class="item-na"]/text()')
        if "is no longer available." in " ".join(arr):
            return 1
        else:
            arr = self.tree_html.xpath('//span[@class="price-sales"]/text()')
            if "N/A" in " ".join(arr):
                return 1
        return 0

    def _sku(self):
        sku = re.search('"product_sku":(.*?)],', html.tostring(self.tree_html), re.DOTALL)

        if sku:
            return sku.group(1).replace("[", "").replace('"', '')

    def _item_num(self):
        item_num = self.tree_html.xpath('//div[contains(@class, "product-number")]'
                                        '/span/text()')
        if item_num:
            return item_num[0]

    def _bullets(self):
        return '\n'.join(
            [x.strip() for x in self.tree_html.xpath('//div[@class="product-main-attributes"]//span/text()')]
        )

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//div[contains(@class, "product-thumbnails")]'
                                          '/ul/li/a/img[contains(@class, "productthumbnail")]'
                                          '/@src')
        return image_urls

    def _size_chart(self):
        if self.tree_html.xpath('//table[contains(@class, "size-chart")]'):
            return 1

        return 0

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price_sale = self.tree_html.xpath('//div[contains(@class, "product-price")]'
                                          '//span[@class="price-sales"]'
                                          '/text()')
        special_price = self.tree_html.xpath('//div[contains(@class, "product-price")]'
                                             '/div/text()')
        promo_price = self.tree_html.xpath('//div[contains(@class, "product-price")]'
                                           '/span[@class="price-promo"]/text()')
        if price_sale:
            price = price_sale[0]
        elif len(special_price) > 1:
            min_price = special_price[0].split('-')[0].strip()
            max_price = special_price[0].split('-')[1].strip()
            price = min_price + '-' + max_price
        elif promo_price:
            price = promo_price[0]

        return self._clean_text(price) if price else None

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self._no_longer_available():
            return 1

        stock_info = self.tree_html.xpath('//*[@property="og:availability"]/@content')
        if stock_info and "instock" not in stock_info[0]:
            return 1
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        return self.tree_html.xpath('//div[contains(@class, "breadcrumb")]/a/text()')

    def _brand(self):
        brand = re.search('"product_brand":(.*?)],', html.tostring(self.tree_html), re.DOTALL)

        if brand:
            return brand.group(1).replace("[", "").replace('"', '').strip()

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
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "description": _description,
        "sku": _sku,
        "item_num": _item_num,
        "variants": _variants,
        "no_longer_available": _no_longer_available,
        "bullets": _bullets,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "size_chart": _size_chart,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
