#!/usr/bin/python

import re

from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words
from spiders_shared_code.ebay_variants import EbayVariants


class EbayScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://(cgi|www).ebay.com/<product id>"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.desc_html = None
        self.eb = EbayVariants()

    def check_url_format(self):
        m = re.match('https?://(cgi|www).ebay.com/.*', self.product_page_url)
        return bool(m)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')
        if not itemtype or (itemtype and itemtype[0] != "ebay-objects:item"):
            return True

        self._extract_full_desc()
        self.eb.setupCH(self.tree_html)

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_full_desc(self):
        desc_href = self.tree_html.xpath("//div[@class='u-padB20']//a/@href")
        iframe_desc = self.tree_html.xpath("//iframe[@id='desc_ifr']/@src")
        response = None
        if desc_href:
            response = self._request(desc_href[0])
        elif iframe_desc:
            response = self._request(iframe_desc[0])

        if response and response.ok:
            content = response.text
            self.desc_html = html.fromstring(content)

    def _product_id(self):
        product_id = self.tree_html.xpath("//div[@id='descItemNumber']/text()")
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[@itemprop='name']/text()")
        return product_name[0] if product_name else None

    def _product_title(self):
        return self._product_name()

    def _model(self):
        model = None
        details = self.tree_html.xpath("//div[@class='prodDetailSec']//tr")
        for detail in details:
            model_key = detail.xpath(".//td/text()")
            if model_key and ('Model' in model_key[0]):
                model = model_key
                break
        if not model:
            model = self.tree_html.xpath("//h2[@itemprop='mpn']/text()")
        return self._clean_text(model[-1]) if model else None

    def _mpn(self):
        mpn = self.tree_html.xpath("//h2[@itemprop='mpn']/text()")
        return mpn[0] if mpn else None

    def _upc(self):
        upc = self.tree_html.xpath("//h2[@itemprop='gtin13']/text()")
        return upc[0] if upc else None

    def _description(self):
        desc = self.tree_html.xpath("//span[@class='expSvcText']/text() | "
                                    "//div[@class='vi_descsnpt_holder']/text()")
        if desc:
            desc = self._clean_text(desc[0])
        if not desc and self.desc_html:
            desc_html = self.desc_html.xpath("//div[@id='descriptioncontent']//p")
            for data in desc_html:
                if 'Description:' in data.xpath(".//span/text()")[0]:
                    desc = data.xpath(".//span/text()")[-1]
                    break
        return desc if desc else None

    def _long_description(self):
        desc = None
        full_desc_title = []
        if self.desc_html:
            full_desc_title = self.desc_html.xpath("//div[@class='blinq-listing-content']//h2/text()")
        for i, attr in enumerate(full_desc_title):
            if attr.lower() == 'description':
                desc = html.tostring(self.desc_html.xpath("//div[@class='blinq-listing-content']//ul")[i])
        return desc

    def _features(self):
        features = None
        feature_html = []
        full_desc_title = []

        if self.desc_html:
            full_desc_title = self.desc_html.xpath("//div[@class='blinq-listing-content']//h2/text()")
        for i, attr in enumerate(full_desc_title):
            if attr.lower() == 'features':
                features = self.desc_html.xpath("//div[@class='blinq-listing-content']//ul")[i].xpath(".//li/text()")
        if not features:
            full_desc_title = self.tree_html.xpath("//div[@class='itemAttr']//tr")
        for attr in full_desc_title:
            for i, data in enumerate(attr.xpath(".//td/text()")):
                if 'Features:' in data:
                    features = attr.xpath(".//td")[i+1].xpath(".//span/text()")[0].split(',')
                    break
        if not features:
            feature_html = self.desc_html.xpath("//div[@id='descriptioncontent']//p")
        for data in feature_html:
            if 'Features:' in data.xpath(".//span/text()")[0]:
                features = data.xpath(".//span/text()")[1:]
                break
        return features

    def _specs(self):
        specs = {}
        specs_info = None
        specs_html = self.desc_html.xpath("//div[@id='descriptioncontent']//p")
        for data in specs_html:
            if 'Specification:' in data.xpath(".//span/text()")[0]:
                specs_info = data.xpath(".//span/text()")[1:]
                break
        for spec in specs_info:
            specs_key = spec.split(":")[0]
            specs_value = spec.split(":")[-1].strip()
            specs[specs_key] = specs_value
        return specs

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath("//div[@id='vi_main_img_fs']//td[@class='tdThumb']//img/@src")
        if not image_urls:
            image_urls = self.tree_html.xpath("//div[@id='mainImgHldr']//img[@id='icImg']/@src")
        return image_urls

    def _variants(self):
        return self.eb._variants()

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        average_rating = None
        average_rating_info = self.tree_html.xpath("//span[@class='ebay-review-start-rating']/text()")
        if average_rating_info:
            average_rating = re.findall('\d*\.?\d+', average_rating_info[0])
        return float(average_rating[0]) if average_rating else 0

    def _review_count(self):
        review_count = None
        review_info = self.tree_html.xpath("//span[@class='ebay-reviews-count']/text()")
        if review_info:
            review_count = re.search('\d+', review_info[0])

        return int(review_count.group()) if review_count else 0

    def _reviews(self):
        rating_by_star = []
        rating_values = []

        # Get mark of Review
        rating_values_data = self.tree_html.xpath("//div[@id='rwid']//div[@class='ebay-review-item-r']//span/text()")
        for rating_value in rating_values_data:
            rating_values.append(re.findall(r'(\d+)', rating_value)[0])

        for i, attr in enumerate(rating_values):
            rating_by_star.append([5 - i, int(attr)])
        return rating_by_star if rating_by_star else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.tree_html.xpath("//span[@id='prcIsum']/@content | "
                                     "//span[@itemprop='price']/@content")
        return float(price[0]) if price else None

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        oos = self.tree_html.xpath("//span[@itemprop='availability']/@content")
        item_stock = self.tree_html.xpath("//span[@id='w1-4-_msg']/text()")
        if (oos and 'Out Of Stock' in oos[0]) or (item_stock and 'This item is out of stock' in item_stock[0]):
            return 1
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//li[@itemprop='itemListElement']//span[@itemprop='name']/text()")
        return categories if categories else None

    def _brand(self):
        title = self._product_title()
        brand = self.tree_html.xpath("//h2[@itemprop='brand']//span[@itemprop='name']/text()")
        if brand:
            brand = brand[0]
        elif title:
            brand = guess_brand_from_first_words(title)
        return brand

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\r\n\t]", "", text).strip()

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "model": _model,
        "mpn": _mpn,
        "upc": _upc,
        "description": _description,
        "long_description": _long_description,
        "features": _features,
        "specs": _specs,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "variants": _variants,

        # CONTAINER : REVIEWS
        "review_count": _review_count,
        "average_review": _average_review,
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand
        }