#!/usr/bin/python

import re
import urlparse
import requests

from lxml import html
from extract_data import Scraper
from spiders_shared_code.surlatable_variants import SurlatableVariants


class SurlatableScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.surlatable.com/product/<product id>"

    IMAGE_URL_TEMPLATES = "https://www.surlatable.com/images/customers/c1079/{prod_id}/{prod_id}_pdp/main_variation_Default_view_{num}_425x425."

    VIDEO_URL_FORMAT = "https://www.youtube.com/embed/"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.sb = SurlatableVariants()

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def check_url_format(self):
        m = re.match(r"^https?://www.surlatable.com/product/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        self.sb.setupCH(self.tree_html)
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath("//input[@name='productID']/@value")
        return product_id[0] if product_id else None

    def _sku(self):
        sku = self.tree_html.xpath("//input[@name='skuId']/@value")
        return self._clean_text(sku[-1]) if sku else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[@id='product-title']/text()")
        return self._clean_text(product_name[0]) if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _description(self):
        description = ''.join(self.tree_html.xpath("//div[@itemprop='description']/text()"))
        ul_description = self.tree_html.xpath("//div[@itemprop='description']//ul")
        if ul_description:
            description = ''.join([description, html.tostring(ul_description[0])])

        return self._clean_text(description) if description else None

    def _features(self):
        features = self.tree_html.xpath("//div[@id='product-moreInfo-features']//ul//li/text()")
        return features if features else None

    def _specs(self):
        specs = self.tree_html.xpath("//div[@id='product-moreInfo-specs']//ul//li/text()")
        return specs if specs else None

    def _variants(self):
        price_amount = self._price_amount()
        return self.sb._variants(price_amount)

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []
        prod_id = self._product_id()
        if prod_id:
            for i in range(1, 20):
                image_url = self.IMAGE_URL_TEMPLATES.format(prod_id=prod_id, num=i)
                if requests.head(image_url, timeout=5).status_code == 200:
                    image_urls.append(image_url)
        return image_urls

    def _video_urls(self):
        video_urls = []
        video_ids = self.tree_html.xpath("//div/@data-video")
        for v_id in video_ids:
            video_urls.append(urlparse.urljoin(self.VIDEO_URL_FORMAT, v_id))
        return video_urls if video_urls else None

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        average_rating = self.tree_html.xpath("//div[@class='TT2left']//meta[@itemprop='ratingValue']/@content")
        return float(average_rating[0]) if average_rating else 0

    def _review_count(self):
        review_count = self.tree_html.xpath("//div[@class='TT2left']//meta[@itemprop='reviewCount']/@content")
        return int(review_count[0]) if review_count else 0

    def _reviews(self):
        rating_values = []
        rating_mark_list = [[1, 0], [2, 0], [3, 0], [4, 0], [5, 0]]
        for i in range(1, 6):
            rating_value = self.tree_html.xpath("//div[@id='TTreviewSummaryBreakdown-"+str(i)+"']/text()")
            if rating_value:
                rating_values.append(int(rating_value[0]))
        if rating_values:
            for i in range(0, 5):
                rating_mark_list[i] = [i + 1, rating_values[i]]
        buyer_reviews_info = rating_mark_list[::-1]

        return buyer_reviews_info

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.tree_html.xpath("//span[@itemprop='price']/text()")
        return float(price[0]) if price else None

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = []
        breadcrumbs = self.tree_html.xpath("//div[@id='product-breadcrumbs']//span")
        for ct in breadcrumbs:
            if '<a ' in html.tostring(ct):
                category = ct.xpath(".//a/text()")
                if category:
                    categories.append(self._clean_text(category[0]))
            if '<label ' in html.tostring(ct):
                category = ct.xpath(".//label/text()")
                if category:
                    categories.append(self._clean_text(category[0]))

        return categories if categories else None

    def _brand(self):
        brand = self.tree_html.xpath("//span[@itemprop='brand']/text()")
        return brand[0] if brand else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\r\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "sku": _sku,
        "description": _description,
        "features": _features,
        "specs": _specs,
        "variants" : _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : REVIEWS
        "review_count": _review_count,
        "average_review": _average_review,
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand
        }

