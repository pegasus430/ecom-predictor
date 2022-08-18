# !/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import json
import re
import urlparse

import requests
from extract_data import Scraper
from lxml import html


import spiders_shared_code.canonicalize_url
from spiders_shared_code.johnlewis_variants import JohnLewisVariants


class JohnlewisScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.johnlewis.com/<product-name>/<product-id>"
    REVIEW_URL = "https://johnlewis.ugc.bazaarvoice.com/7051onejl-en_gb/{0}/reviews.djs?format=embeddedhtml"

    def __init__(self, **kwargs):  # **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        # whether product has any webcollage media
        self.jlv = JohnLewisVariants()
        self.product_json = None
        self.review_json = None
        self.rev_list = None
        self.is_review_checked = False

    def canonicalize_url(self, url):
        return spiders_shared_code.canonicalize_url.johnlewis(url)

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://www.johnlewis.com/.*/.*?$", self.product_page_url)
        return not not m

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _canonical_link(self):
        return self.tree_html.xpath("//link[@rel='canonical']/@href")[0]

    def _url(self):
        return self.product_page_url

    def _event(self):
        return None

    def _product_id(self):
        return re.search('/p(\d+)', self.product_page_url).group(1)

    def _site_id(self):
        return None

    def _status(self):
        return "success"

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath(".//*[@id='prod-title']/span/text()")[0]

    def _product_title(self):
        return self.tree_html.xpath(".//*[@id='prod-title']/span/text()")[0]

    def _title_seo(self):
        return self._product_title()

    def _model(self):
        return None

    def _upc(self):
        return None

    def _features(self):
        return None

    def _feature_count(self):
        return None

    def _model_meta(self):
        return None

    def _description(self):
        desc = self.tree_html.xpath('.//div[@id="prod-info-tab"]//span[@itemprop="description"]//text()')
        desc = self._clean_text("".join(desc))
        return desc

    def _long_description(self):
        return self._description()

    def _swatches(self):
        swatches = []

        for color in self.tree_html.xpath('.//*[@id="prod-product-colour"]//li'):
            swatch = {
                'color': color.xpath('.//img/@title')[0],
                'hero': 1,
                'hero_image': "http://{}".format(color.xpath('.//img/@src')[0]),
            }

            swatches.append(swatch)

        if swatches:
            return swatches

    def _variants(self):
        self.jlv.setupCH(self.tree_html)
        self.variants = self.jlv._variants(self.product_page_url)
        return self.variants

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        image_urls = []

        for image in self.tree_html.xpath('.//*[@class="thumbnails"]//img/@src'):
            image = image.split("?")[0]
            image_urls.append(urlparse.urljoin(self.product_page_url, image))
        return image_urls

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    def _video_urls(self):
        return None

    def _video_count(self):
        return None

    def _wc_360(self):
        return 0

    def _wc_video(self):
        return None

    def _pdf_urls(self):
        return None

    def _pdf_count(self):
        return 0

    def _webcollage(self):
        return 0

    def _htags(self):
        htags_dict = {}
        # add h1 tags text to the list corresponding to the "h1" key in the dict
        htags_dict["h1"] = map(lambda t: self._clean_text(t),
                               self.tree_html.xpath("//h1//text()[normalize-space()!='']"))
        # add h2 tags text to the list corresponding to the "h2" key in the dict
        htags_dict["h2"] = map(lambda t: self._clean_text(t),
                               self.tree_html.xpath("//h2//text()[normalize-space()!='']"))
        return htags_dict

    def _keywords(self):
        return None

        ##########################################
        ############### CONTAINER : REVIEWS
        ##########################################

    def _average_review(self):
        if self._review_count() == 0:
            return None

        average_review = round(float(self.review_json["jsonData"]["attributes"]["avgRating"]), 1)

        if str(average_review).split('.')[1] == '0':
            return int(average_review)
        else:
            return float(average_review)

    def _review_count(self):
        self._reviews()

        if not self.review_json:
            return 0

        return int(self.review_json["jsonData"]["attributes"]["numReviews"])

    def _max_review(self):
        if self._review_count() == 0 or not self.review_list:
            return None

        for i, review in enumerate(self.review_list):
            if review[1] > 0:
                return 5 - i

    def _min_review(self):
        if self._review_count() == 0 or not self.review_list:
            return None

        for i, review in enumerate(reversed(self.review_list)):
            if review[1] > 0:
                return i + 1

    def _reviews(self):
        # TODO fix review_list extraction if possible
        if self.is_review_checked:
            return self.review_list

        self.is_review_checked = True
        review_id = self._product_id()
        # contents = self.load_page_from_url_with_number_of_retries()
        contents = requests.get(self.REVIEW_URL.format(review_id), timeout=20).text
        try:
            start_index = contents.find("webAnalyticsConfig:") + len("webAnalyticsConfig:")
            end_index = contents.find(",\nwidgetInitializers:initializers", start_index)

            self.review_json = contents[start_index:end_index]
            self.review_json = json.loads(self.review_json)
        except:
            self.review_json = None

        review_html = html.fromstring(
            re.search('"BVRRSecondaryRatingSummarySourceID":" (.+?)"},\ninitializers={', contents).group(1))
        reviews_by_mark = review_html.xpath("//*[contains(@class, 'BVRRHistAbsLabel')]/text()")
        reviews_by_mark = reviews_by_mark[:5]
        review_list = [[5 - i, int(re.findall('\d+', mark)[0])] for i, mark in enumerate(reviews_by_mark)]

        if not review_list:
            review_list = None
        self.review_list = review_list

        return self.review_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath('.//*[@class="now-price"]/text()')
        if not price:
            price = self.tree_html.xpath('.//*[@class="basket-fields"]//strong[@class="price"]/text()')
        price = price[0].strip() if price else None
        return price

    def _price_amount(self):
        price = self.tree_html.xpath('.//*[@class="now-price"]/text()')
        if not price:
            price = self.tree_html.xpath('.//*[@class="basket-fields"]//strong[@class="price"]/text()')
        price = price[0].strip() if price else None
        price = re.search('\d+\.?\d+', price).group()
        return float(price)

    def _price_currency(self):
        price = self.tree_html.xpath('.//*[@class="now-price"]/text()')
        if not price:
            price = self.tree_html.xpath('.//*[@class="basket-fields"]//strong[@class="price"]/text()')
        price = price[0].strip() if price else None
        currency = self.tree_html.xpath('.//*[@itemprop="pricecurrency"]/@content')
        currency = currency[0] if currency else None
        if not currency and '£' in price:
            currency = "GBP"
        if not currency:
            currency = "USD"
        return currency

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self.tree_html.xpath('.//p[starts-with(@class,"out-of-stock")]'):
            return 1
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    def _seller_from_tree(self):
        return None

    def _marketplace_sellers(self):
        return None

    def _marketplace_lowest_price(self):
        return None

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        return self.tree_html.xpath(".//*[@id='breadcrumbs']//li/a[not(@href='/')]/text()")

    def _category_name(self):
        return self._categories()[-1]

    def _brand(self):
        return self.tree_html.xpath('.//*[@itemprop="brand"]/span[@itemprop="name"]/text()')[0].strip()

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces
    def _clean_text(self, text):
        return re.sub('[\r\n\t]', '', text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "url": _url, \
        "event": _event, \
        "product_id": _product_id, \
        "site_id": _site_id, \
        "status": _status, \
 \
        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name, \
        "product_title": _product_title, \
        "title_seo": _title_seo, \
        "model": _model, \
        "upc": _upc, \
        "features": _features, \
        "feature_count": _feature_count, \
        "model_meta": _model_meta, \
        "description": _description, \
        "long_description": _long_description, \
        "swatches": _swatches, \
        "variants": _variants, \
 \
        # CONTAINER : PAGE_ATTRIBUTES
        "image_count": _image_count, \
        "image_urls": _image_urls, \
        "video_count": _video_count, \
        "video_urls": _video_urls, \
        "pdf_count": _pdf_count, \
        "pdf_urls": _pdf_urls, \
        "webcollage": _webcollage, \
        "wc_360": _wc_360, \
        "wc_video": _wc_video, \
        "htags": _htags, \
        "keywords": _keywords, \
        "canonical_link": _canonical_link, \
 \
        # CONTAINER : REVIEWS
        "review_count": _review_count, \
        "average_review": _average_review, \
        "max_review": _max_review, \
        "min_review": _min_review, \
        "reviews": _reviews, \
 \
        # CONTAINER : SELLERS
        "price": _price, \
        "price_amount": _price_amount, \
        "price_currency": _price_currency, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "in_stores_out_of_stock": _in_stores_out_of_stock, \
        "marketplace": _marketplace, \
        "marketplace_sellers": _marketplace_sellers, \
        "marketplace_lowest_price": _marketplace_lowest_price, \
 \
        # CONTAINER : CLASSIFICATION
        "categories": _categories, \
        "category_name": _category_name, \
        "brand": _brand, \
 \
        "loaded_in_seconds": None, \
        }

    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = { \
        "mobile_image_same": _mobile_image_same, \
        }

