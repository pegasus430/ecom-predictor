#!/usr/bin/python

import re
from lxml import html

from extract_data import Scraper

class WillamsSonomaScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.williams-sonoma.com/products/.*"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?passkey=35scpqb6wtdhtvrjdydkd7d6v&" \
                 "apiversion=5.5&displaycode=3177-en_us&" \
                 "resource.q0=products&" \
                 "filter.q0=id%3Aeq%3A{}&" \
                 "stats.q0=reviews&" \
                 "filteredstats.q0=reviews"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

    def check_url_format(self):
        m = re.match(r"^https?://www.williams-sonoma.com/products/.*$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[@id="pip"]')) < 1:
            return True
        return False

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = re.search("productId : '(.*?)'", html.tostring(self.tree_html), re.DOTALL)
        if product_id:
            return product_id.group(1)

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//div[@class="pip-summary"]/h1/text()')
        if product_name:
            return product_name[0].strip()

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _model(self):
        model = re.search('Model #(.*?)<', html.tostring(self.tree_html))
        return model.group(1) if model else None

    def _description(self):
        description = self.tree_html.xpath('//div[contains(@class, "accordion-contents")]//text()')
        description = self._clean_text(' '.join(description))
        return description

    def _brand(self):
        brand = re.search('brand:"(.*?)"', html.tostring(self.tree_html))
        return brand.group(1) if brand else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//div[@class="image-container"]//ul/li'
                                          '/a[contains(@class, "thumbnailWidget")]/img/@src')
        return image_urls

    def _video_urls(self):
        video_urls = self.tree_html.xpath('//div[@class="image-container"]//ul/li'
                                          '/a[contains(@class, "videoThumbnail")]/@data-thumbnail')
        video_list = []
        for video in video_urls:
            video_url = re.search("id: '(.*?)'", video, re.DOTALL)
            if video_url:
                video_list.append('https://youtu.be/' + video_url.group(1))
        return video_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath('//span[contains(@class, "price-special")]//span[@class="price-amount"]/text()')
        if not price:
            price = self.tree_html.xpath('//span[@class="price-amount"]/text()')
        return '$' + price[0]

    def _in_stores(self):
        online_only = self.tree_html.xpath('//li[contains(@class, "flag-onlineOnly")]')
        if online_only:
            return 0
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        return self.tree_html.xpath('//ul[@id="breadcrumb-list"]//a/span[@itemprop="name"]/text()')

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo": _title_seo,
        "model": _model,
        "description": _description,
        "brand": _brand,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
    }
