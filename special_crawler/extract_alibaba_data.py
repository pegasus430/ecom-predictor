#!/usr/bin/python

import re
import urlparse
import json
import traceback

from lxml import html

from extract_data import Scraper


class AlibabaScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://(www.)alibaba.com/product-detail/<product-name>"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self._set_proxy()
        self.checked_specs = False

    def check_url_format(self):
        m = re.match(r"https?://(www.)?alibaba.com/product-detail/.*?", self.product_page_url)
        return bool(m)

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')
        if itemtype and itemtype[0].strip() == 'product':
            return False

        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = re.search(r'_(\d+).html', self.product_page_url)
        return product_id.group(1) if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[@class='ma-title']/text()")
        if not product_name:
            product_name = self.tree_html.xpath("//h1[@class='ma-title']//span[@class='ma-title-text']/text()")
        return product_name[0] if product_name else None

    def _brand(self):
        if self.checked_specs is False:
            self._specs()

        return self.brand

    def _product_title(self):
        return self._product_name()

    def _model(self):
        if self.checked_specs is False:
            self._specs()

        return self.model

    def _specs(self):
        specs = {}
        self.checked_specs = True
        specs_groups = self.tree_html.xpath("//div[@class='do-entry-list']//dl[@class='do-entry-item']")
        for spec in specs_groups:
            spec_name = spec.xpath(".//dt[@class='do-entry-item']//span[contains(@class, 'attr-name')]/text()")
            spec_value = spec.xpath(".//dd[@class='do-entry-item-val']//div[@class='ellipsis']/text()")
            if spec_name and spec_value:
                spec_name = spec_name[0]
                spec_value = spec_value[0]
                specs.update({spec_name: spec_value})
            else:
                continue

            if 'Brand Name' in spec_name:
                self.brand = spec_value
            if 'Model Number' in spec_name:
                self.model = spec_value

        return specs if specs else None

    def _no_longer_available(self):
        return 0

    def _description(self):
        description = self.tree_html.xpath(
            '//div[contains(@id, "text-description")]//div[@data-section-title="Product Description"]//p | '
            '//div[contains(@id, "text-description")]//p[./preceding-sibling::'
            'div[@data-section-title="Product Description"]]'
        )
        return self._clean_text(
            ' '.join([x.text_content() for x in description if x.text_content().strip() != ''])
        ) if description else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath("//ul[contains(@class, 'inav')]//div[@class='thumb']//img/@src")
        return [urlparse.urljoin(self.product_page_url, image_url.replace('_50x50.jpg', ''))
                for image_url in image_urls] if image_urls else None

    def _video_urls(self):
        videos = []
        medias = []
        media_data = self._find_between(html.tostring(self.tree_html), 'type="application/ld+json">', '</script>')
        try:
            medias = json.loads(media_data)
        except:
            print traceback.format_exc()

        for media in medias:
            if media.get('@type') == 'VideoObject' and media.get('contentUrl'):
                videos.append(urlparse.urljoin(self.product_page_url, media.get('contentUrl')))

        return videos if videos else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.tree_html.xpath("//div[@class='ma-spec-price']//span[@class='pre-inquiry-price']/text()")
        if not price:
            price = self.tree_html.xpath(
                "//div[@class='ma-reference-price']"
                "//span[@class='ma-ref-price']"
                "//span[not(@content='USD')]/text()"
            )
        if price:
            price = float(price[0])

            return price

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.tree_html.xpath(
            "//ol[@class='detail-breadcrumb']"
            "//li[@class='breadcrumb-item']"
            "//a//span[not(@class='bread-count')]/text()"
        )
        categories = [self._clean_text(category) for category in categories if self._clean_text(category)]
        return categories[1:] if categories else None

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
        "brand": _brand,
        "model": _model,
        "specs": _specs,
        "no_longer_available": _no_longer_available,
        "description": _description,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # # CONTAINER : CLASSIFICATION
        "categories": _categories,
        }
