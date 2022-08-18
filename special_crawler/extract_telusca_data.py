# -*- coding: utf-8 -*-
#!/usr/bin/python

import re
import urlparse

from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words
from spiders_shared_code.telusca_variants import TelusCAVariants


class TelusCAScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is (http|https)://(www.)?telus.com/en/.*"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.tv = TelusCAVariants()

    def check_url_format(self):
        m = re.match(r"^(http|https)://(www.)?telus.com/en/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        self.tv.setupCH(self.tree_html)

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self._find_between(html.tostring(self.tree_html), 'PID = ', ';').strip()

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_title = self.tree_html.xpath("//*[contains(@class, 'product-feature__title')]/text()")

        if not product_title:
            product_title = self.tree_html.xpath("//h1[@id='page-title']/text()")

        if not product_title:
            product_title = self.tree_html.xpath(
                "//div[@class='device-config__device-name']//h1/text()"
            )

        if not product_title:
            product_title = self.tree_html.xpath(
                "//div[contains(@class, 'page-title')]//h2/text()"
            )

        if not product_title:
            product_title = self.tree_html.xpath("//title/text()")

        if product_title:
            product_title = re.sub(u'\u2013|TELUS.com|- TELUS.com|Mobility|\|', '', product_title[0]).strip()
            return product_title

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _long_description(self):
        feature_blocks = self.tree_html.xpath("//div[@class='collapsible-panel']")

        for block in feature_blocks:
            if 'Specifications' in block.xpath(".//*[@class='collapsible-panel__header']/text()"):
                long_desc = block.xpath(".//div[@class='collapsible-panel__content']")
                if long_desc:
                    long_desc = self._clean_text(html.tostring(long_desc[0]))

                    return long_desc

    def _sku(self):
        sku = re.search(r'"sku":"(.*?)"', self.page_raw_text)
        if sku:
            return sku.group(1)

    def _upc(self):
        upc = re.search(r'"upc":(.*?),"', self.page_raw_text)
        if upc:
            return upc.group(1)

    def _variants(self):
        return self.tv._variants()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        images = self.tree_html.xpath(
            "//div[@class='product-detail-slide__carousel']"
            "//ul[@class='carousel__links']"
            "//li[contains(@class, 'carousel__link')]//img/@src"
        )

        domain = 'https:'
        if images:
            return [urlparse.urljoin(domain, image) for image in images]

        hero = self.tree_html.xpath("//div[@class='product-image']//img/@src")
        if hero:
            return [urlparse.urljoin(domain, h) for h in hero]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price_no_term = None
        price_groups = self.tree_html.xpath("//div[contains(@class, 'price-options__item')]")
        for price_group in price_groups:
            if 'No term' in html.tostring(price_group):
                price_no_term = price_group.xpath(".//span[contains(@class, 'price-options__tier-price')]"
                                                  "//span/text()")

        if price_no_term:
            return float(re.sub(r'[$,]', '', price_no_term[0]))

        xpathes = "//h2[contains(@class, 'product-sale__title')]/@content |" \
                  "//p[@itemprop='price']/text() |" \
                  "//span[contains(@class, 'price-options__tier-price')]//span/text() |" \
                  "//h2[contains(@class, 'product-sale__title')]/text() |" \
                  "//div[@class='no-term']//h4//span/text() |" \
                  "//div[@class='detail-price']//div[@class='device-balance']" \
                  "//div[@class='no-term']//h4//span/text()"

        price = self.tree_html.xpath(xpathes)

        if price:
            return float(re.sub(r'[$,]', '', price[0]))

    def _price_currency(self):
        return 'CAD'

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        brand = self.tree_html.xpath(
            "//*[contains(@class, 'product-feature__brand')]/text()"
        )

        if not brand:
            brand = self.tree_html.xpath(
                "//div[@class='device-config__device-name']//p/text()"
            )

        if brand:
            brand = brand[0]
        else:
            brand = guess_brand_from_first_words(self._product_name())

        return brand

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id" : _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "long_description" : _long_description, \
        "sku": _sku, \
        "upc": _upc, \
        "variants" : _variants, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls, \

        # CONTAINER : REVIEWS

        # CONTAINER : SELLERS
        "price_amount" : _price_amount, \
        "price_currency" : _price_currency, \
        "site_online" : _site_online, \
        "site_online_out_of_stock" : _site_online_out_of_stock, \

        # CONTAINER : CLASSIFICATION
        "brand" : _brand, \
        }
