#!/usr/bin/python

import re
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words


class TotalwineScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.totalwine.com/<department-name>/<category-name>/<product-name>/<product id>"

    REVIEW_URL = "https://totalwine.ugc.bazaarvoice.com/6595-en_us/{0}/reviews.djs?format=embeddedhtml"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self._set_proxy()

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries(use_session = True)

    def check_url_format(self):
        m = re.match(r"^https?://www.totalwine.com/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath("//input[@id='productCode']/@value")
        return product_id[-1] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[@class='product-name']/text()")
        return self._clean_text(product_name[-1]) if product_name else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _video_urls(self):
        video_list = []
        video_domain = "https://vimeo.com/"
        video_id = self.tree_html.xpath("//div[contains(@class, 'pdp-img-zoom-modal-video')]/@data-video")

        for id in video_id:
            video_list.append(video_domain + id)
        return video_list

    def _image_urls(self):
        image_url_list = []
        image_urls = self.tree_html.xpath("//div[contains(@class, 'pdp-tab-overview-prod-img-bottle-img')]//img/@src")
        if image_urls:
            for image_url in image_urls:
                image_url_list.append('http://www.totalwine.com' + image_url)

        return image_url_list

    def _description(self):
        short_description = self.tree_html.xpath("//div[@class='right-full-desc']//p/text()")

        if short_description:
            return short_description[0].strip()

    def _sku(self):
        sku = self.tree_html.xpath("//meta[@itemprop='sku']/@content")
        return sku[0] if sku else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.tree_html.xpath("//input[@id='anPRice']/@value")
        return float(price[0]) if price else None

    def _in_stores(self):
        stock_status = self.tree_html.xpath('//p[@class="availability-msg"]/text()')
        if stock_status and 'by store' in stock_status[0].lower():
            return 1
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        stock_status = self.tree_html.xpath('//p[@class="availability-msg"]/text()')
        if stock_status and 'instock' in stock_status[0].lower():
            return 0
        return 1

    def _in_stores_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//div[@class='breadcrumbs']//li//a/text()")
        return categories[1:] if categories else None

    def _brand(self):
        brand = self.review_json["jsonData"]['brand']
        if not brand:
            brand = guess_brand_from_first_words(self._product_name())
        return brand

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
        "description": _description,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        "sku": _sku
        }
