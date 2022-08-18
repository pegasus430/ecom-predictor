#!/usr/bin/python

import os
import re
import json
import traceback

from selenium import webdriver
from lxml import html
from extract_data import Scraper, deep_search
from spiders_shared_code.kohls_variants import KohlsVariants

CWD = os.path.dirname(os.path.abspath(__file__))
driver_path = os.path.join(CWD, 'bin', 'chromedriver')
driver_log_path = os.path.join(CWD, 'bin', 'driver.log')


class KohlsScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.kohls.com/product/prd-<product-id>/<optional-part-of-product-name>"
    REVIEW_URL = "http://kohls.ugc.bazaarvoice.com/9025/{}/reviews.djs?format=embeddedhtml"
    WEBCOLLAGE_POWER_PAGE = "http://content.webcollage.net/kohls/power-page?ird=true&channel-product-id={}"
    WEBCOLLAGE_MODULE_PAGE = "http://content.webcollage.net/apps/cs/mini-site/kohls/module/waterpik/wcpc/1482120568609?channel-product-id={}"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.failure_type = None
        self.product_info_json = None
        self.kv = KohlsVariants()

        self.product_page_url = re.sub('https://', 'http://', self.product_page_url)

        self._set_proxy()

    def _get_page_source_web_driver(self, url, attempts=1, wait=5):
        options = webdriver.ChromeOptions()
        options.add_argument('headless')
        browser = None
        for _ in range(0, attempts):
            try:
                browser = webdriver.Chrome(
                    executable_path=driver_path,
                    service_log_path=driver_log_path,
                    chrome_options=options
                )
                browser.set_window_size(1440, 900)
                browser.implicitly_wait(wait)
                browser.set_page_load_timeout(wait)
                browser.get(url)
                return browser.page_source
            except Exception as e:
                if self.lh:
                    self.lh.add_log(
                        'Page {url} not loaded, wait={wait}, error message: {msg}'.format(
                            url=url,
                            wait=wait,
                            msg=e.message
                        )
                    )
            finally:
                if browser is not None:
                    browser.quit()

    def _extract_page_tree(self):
        source_withjs = self._get_page_source_web_driver(self.product_page_url, attempts=3, wait=60)
        if source_withjs:
            self.page_raw_text = source_withjs
            self.tree_html = html.fromstring(self.page_raw_text)
            return

        Scraper._extract_page_tree_with_retries(self, max_retries=5)

    def check_url_format(self):
        m = re.match('https?://www.kohls.com/product/prd-(\d+)', self.product_page_url)
        if m:
            self.product_id = m.group(1)
        return bool(m)

    def not_a_product(self):
        try:
            self._failure_type()

            if self.failure_type:
                self.ERROR_RESPONSE["failure_type"] = self.failure_type
                return True
        except Exception:
            return True

    def _pre_scrape(self):
        self.kv.setupCH(self.tree_html)

        self.product_info_json = self.kv._extract_product_info_json()

        self._extract_webcollage_contents()

        if not self._webcollage() and self._brand() == 'waterpik':
            self._extract_webcollage_module_contents() 

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.product_id

    def _is_out_of_stock(self):
        try:
            message = html.tostring(self.tree_html.xpath('//div[@id="content"]/p')[0])
            message = re.sub('[\r\n\t]', '', message)

            if re.match('<p><strong>We&#8217;re very sorry, this item</strong><b>.+</b><strong> is out of stock.</strong></p>', message):
                return True
        except:
            return False

    def _failure_type(self):
        itemtype = self.tree_html.xpath('//div[@itemtype="http://schema.org/Product"]')

        if self._is_out_of_stock():
            return

        if not itemtype:
            self.failure_type = "Not a product"
            return

        if "var page = 'collectionPDPPage';" in self.page_raw_text:
            self.failure_type = "Collection product"
            return

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _out_of_stock_product_name(self):
        return self.tree_html.xpath('//div[@id="content"]/p/b/text()')[0]

    def _product_name(self):
        if self._is_out_of_stock():
            return self._out_of_stock_product_name()
        return self.tree_html.xpath('//title/text()')[0].strip()

    def _features(self):
        features_title_list = ["Product Features:", "PRODUCT FEATURES", "Product Features", "Features"]

        description_block = self.tree_html.xpath('//div[contains(@id,"productDetail")]/div')

        if description_block:
            for element_block in description_block[0]:
                inner_text = ''.join([t.strip() for t in element_block.itertext()])

                if inner_text in features_title_list:
                    features_block = element_block.xpath('.//following-sibling::ul')
                    if features_block:
                        return [f.text_content() for f in features_block[0].xpath('.//li')]

    def _description(self):
        meta_description = deep_search('metaDescription', self.product_info_json)

        if meta_description:
            return meta_description[0].strip()

    def _long_description(self):
        features_title_list = ["Product Features:", "PRODUCT FEATURES", "Product Features", "Features"]

        description_block = self.tree_html.xpath('//div[contains(@id,"productDetail")]/div')

        if description_block:
            long_description = ''

            if self._features():
                features_ul = False

                for element_block in description_block[0]:
                    if html.tostring(element_block).startswith("<!--"):
                        continue

                    inner_text = ''.join([t.strip() for t in element_block.itertext()])

                    if inner_text in features_title_list:
                        features_ul = True

                    if features_ul:
                        if not element_block.xpath('./em'):
                            long_description += html.tostring(element_block)
            else:
                is_long_description = False

                for element_block in description_block:
                    if not is_long_description and element_block.tag == 'ul':
                        is_long_description = True

                    if is_long_description:
                        long_description += html.tostring(element_block)

            long_description = self._clean_text(long_description).strip()

            return long_description if long_description else None

    def _variants(self):
        return self.kv._variants()

    def _no_longer_available(self):
        if self._is_out_of_stock():
            return 1
        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []

        for image in self.tree_html.xpath('//a[@class="altImageLink"]'):
            image_urls.append(image.get('rel'))

        return image_urls if image_urls else None

    def _video_urls(self):
        videos = self.tree_html.xpath('//a[@id="altVideoLink"]/@href')
        if self.wc_videos:
            videos.extend(self.wc_videos)
        return videos if videos else None

    def _size_chart(self):
        if self.tree_html.xpath('//div[contains(@id,"sizing")]'):
            return 1
        return 0

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        def format_price(price):
            min_price = price.get('minPrice')
            max_price = price.get('maxPrice')
            if max_price:
                return '${}-${}'.format(min_price, max_price)
            return '${}'.format(min_price)

        sale_price = self.product_info_json.get('price', {}).get('salePrice')
        if sale_price:
            return format_price(sale_price)

        price = self.product_info_json.get('price', {}).get('regularPrice', {})
        return format_price(price)

    def _in_stores(self):
        if self.product_info_json.get('isStoreAvailable'):
            return 1
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self.product_info_json.get('productStatus') == 'InStock':
            return 1
        return 0

    def _marketplace(self):
        return 0

    def _temp_price_cut(self):
        if self.product_info_json.get('price', {}).get('salePrice'):
            return 1
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################    

    def _brand(self):
        brand = deep_search('brand', self.product_info_json)
        if brand:
            return brand[0].get('value')

    def _categories(self):
        categories = deep_search('adUnit', self.product_info_json)
        if categories and categories[0].get('value'):
            return categories[0]['value'].split('/')[1:]

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "features" : _features,
        "description" : _description,
        "long_description" : _long_description,
        "variants" : _variants,
        "no_longer_available" : _no_longer_available,
        "categories" : _categories,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "video_urls" : _video_urls,
        "size_chart" : _size_chart,

        # CONTAINER : SELLERS
        "price" : _price,
        "marketplace" : _marketplace,
        "site_online" : _site_online,
        "site_online_out_of_stock" : _site_online_out_of_stock,
        "in_stores" : _in_stores,
        "temp_price_cut" : _temp_price_cut,

        # CONTAINER : CLASSIFICATION
        "brand" : _brand,
        }
