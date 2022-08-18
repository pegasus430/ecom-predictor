#!/usr/bin/python

import re
import urlparse
from lxml import html

from extract_data import Scraper
from spiders_shared_code.vitacost_variants import VitacostVariants


class VitacostScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://(www.)vitacost.com/<product-name>"

    REVIEW_URL = 'https://api.bazaarvoice.com/data/batch.json?passkey=pgtdnhg3w0npen2to8bo3bbqn&apiversion=5.5' \
                 '&displaycode=4595-en_us&resource.q0=products&filter.q0=id:eq:{}&stats.q0=reviews'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self._set_proxy()
        self.vv = VitacostVariants()

    def check_url_format(self):
        m = re.match(r"https?://(www.)?vitacost.com/.*?", self.product_page_url)
        return bool(m)

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def not_a_product(self):
        self.vv.setupCH(self.tree_html)
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath("//*[@id='bb-productID']/@value")
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//div[@id='pdTitleBlock']//h1/text()")
        return product_name[0] if product_name else None

    def _brand(self):
        brand = self.tree_html.xpath("//*[contains(@class, 'pBrandNameM')]/text()")
        return brand[0] if brand else None

    def _product_title(self):
        return self._product_name()

    def _description(self):
        short_description = self.tree_html.xpath("//meta[@name='twitter:description']//@content")
        return short_description[0] if short_description else None

    def _long_description(self):
        description = self.tree_html.xpath("//div[@id='productDetails']/descendant::text()")

        return self._clean_text(''.join(description)) if description else None

    def _no_longer_available(self):
        return 0

    def _sku(self):
        sku = self.tree_html.xpath("//div[@id='pdTitleBlock']//ul[@class='link-line']//li/text()")
        sku = re.search(r'\d+', ''.join(sku))
        return sku.group() if sku else None

    def _variants(self):
        return self.vv._variants()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath("//div[@id='productImage']//img/@src")
        return [urlparse.urljoin(self.product_page_url, image_url) for image_url in image_urls] if image_urls else None

    def _video_urls(self):
        video_url = self.tree_html.xpath('//iframe/@src')
        return video_url if video_url else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//*[@id='blockPriceRating']//p[contains(@class, 'pOurPrice')]/text()")
        if price:
            price = price[0].replace('Our price:', '').strip()
            return price

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return int(bool(self.tree_html.xpath("//div[contains(@class, 'pBuyMsgOOS')]")))

    def _in_stores_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.tree_html.xpath("//h3[contains(@class, 'bcs')]//a/text()")
        return categories if categories else None

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "brand" : _brand,
        "description" : _description,
        "long_description" : _long_description,
        "no_longer_available" : _no_longer_available,
        "sku": _sku,
        "variants" : _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "video_urls" : _video_urls,

        # CONTAINER : SELLERS
        "price" : _price,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        }
