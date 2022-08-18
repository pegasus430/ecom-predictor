#!/usr/bin/python

import re
import json
import traceback

from extract_data import Scraper
from lxml import html
from HTMLParser import HTMLParser


class NuevoJumboScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://nuevo.jumbo.cl/<product-name>"

    PRODUCT_JSON_URL = "https://nuevo.jumbo.cl/api/catalog_system/pub/products/search/" \
                       "?sc=4&_from=0&_to=49&fq=productId%3A{item_id}"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.checked_duplicated_images = False
        self.duplicate_images = 0
        self.product_json = {}

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries(save_session=True, use_session=True)

    def _pre_scrape(self):
        self._extract_product_json()

    def _extract_product_json(self):
        item_id = re.search(r'\"productId\":(\d+),', self.page_raw_text)
        if item_id:
            resp = self._request(self.PRODUCT_JSON_URL.format(item_id=item_id.group(1)), session=self.session)
            if resp.status_code == 200:
                self.product_json = resp.json()[0] if isinstance(resp.json(), list) else {}

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath("//div[@class='skuReference']/text()")
        return product_id[0] if product_id else None

    def _product_name(self):
        product_name = self.tree_html.xpath("//div[contains(@class, 'productName')]/text()")
        return product_name[0] if product_name else None

    def _brand(self):
        brand = self.tree_html.xpath("//div[contains(@class, 'brandName')]//a[contains(@class, 'brand')]/text()")
        return brand[0] if brand else None

    def _description(self):
        description = ' '.join(self.product_json.get(u'Campo alfanum\xe9rico', []))
        return description if description else None

    def _long_description(self):
        long_description = re.sub(r'<.*?>', '', self.product_json.get('description', ''))
        return long_description if long_description else None

    def _no_longer_available(self):
        return 0

    def _shelf_description(self):
        shelf_description = self.tree_html.xpath('//div[contains(@class, "description-short")]')
        return self._clean_tags(html.tostring(shelf_description[0])) if shelf_description else None

    def _shelf_description_bullet_count(self):
        shelf_description = self._shelf_description()
        if shelf_description:
            return len(re.findall(r'<li>(.*?)</li>', shelf_description.encode("ascii", "ignore")))

    def _sku(self):
        return self._product_id()

    def _has_ppum(self):
        ppum = self.tree_html.xpath('//*[@class="skuBestPrice"]/@data-ppum')
        if '$0' not in ppum:
            return 1
        return 0

    def _related_products(self):
        return int(bool(self.tree_html.xpath('//div[contains(@class, "related-products")]//ul')))

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = filter(None, self.tree_html.xpath(
            "//div[@class='image-wrapper']//ul[@class='thumbs']"
            "//a[@id='botaoZoom' and not(contains(@zoom, 'producto_en_preparacion'))]/@zoom"))

        if not image_urls:
            image_urls = filter(None, self.tree_html.xpath(
                "//div[@class='image-wrapper']//ul[@class='thumbs']"
                "//a[@id='botaoZoom' and not(contains(@zoom, 'producto_en_preparacion'))]/@rel"))

        if image_urls:
            return image_urls

        main_image = self.tree_html.xpath(
            "//div[@class='image-wrapper']"
            "//div[@id='image']//a[@class='image-zoom']"
            "//img[not(contains(@src, 'producto_en_preparacion'))]/@src"
        )

        return main_image if main_image else None

    def _duplicate_images(self):
        if self.checked_duplicated_images:
            return self.duplicate_images

        self.checked_duplicated_images = True

        image_urls = self._image_urls()
        if image_urls:
            if len(image_urls) == 1:
                self.duplicate_images = 0
            else:
                cl_list = [self._request(image_url, verb='head').headers['content-length'] for image_url in image_urls]

                if cl_list:
                    base_cl_list = list(set(cl_list))
                    self.duplicate_images = len(cl_list) - len(base_cl_list)

            return self.duplicate_images

    def _no_image_available(self):
        return int(bool(self.tree_html.xpath(
            "//a[@id='botaoZoom' and contains(@zoom, 'producto_en_preparacion')]"
        )))

    def _accessories_count(self):
        return len(self.tree_html.xpath('//div[contains(@class, "product-item--accesory")]'))

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//*[@class='skuBestPrice']/text()")
        if price:
            price = price[0].replace('.', '').replace(',', '.')

        return price if price else None

    def _price_currency(self):
        return 'CLP'

    def _temp_price_cut(self):
        list_price = self.tree_html.xpath("//*[@class='skuListPrice']/text()")
        if list_price and list_price[0] != '$ 0,00':
            return 1
        return 0

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return int(self.product_json.get('items', [{}])[0].get('sellers', [{}])[0]
                   .get('commertialOffer', {}).get('AvailableQuantity', 0) <= 0)

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.tree_html.xpath("//div[@class='bread-crumb']//li//a/text()")
        return categories[1:] if categories else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    def _clean_tags(self, text):
        # remove anything between style tags
        text = re.sub(re.compile('<style.*?</style>', re.DOTALL), '', text)
        # remove all tags except for ul/li
        text = re.sub('<(?!ul|li|/ul|/li).*?>', '', text)
        # unescape html codes
        text = HTMLParser().unescape(text)
        return text.strip()

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
        "brand" : _brand,
        "description": _description,
        "long_description": _long_description,
        "no_longer_available": _no_longer_available,
        "shelf_description": _shelf_description,
        "shelf_description_bullet_count": _shelf_description_bullet_count,
        "sku": _sku,
        "has_ppum": _has_ppum,
        "related_products": _related_products,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "duplicate_images": _duplicate_images,
        "no_image_available": _no_image_available,
        "accessories_count": _accessories_count,

        # CONTAINER : SELLERS
        "price": _price,
        "price_currency": _price_currency,
        "temp_price_cut": _temp_price_cut,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # # CONTAINER : CLASSIFICATION
        "categories": _categories,
        }
