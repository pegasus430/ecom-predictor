#!/usr/bin/python

import re
import requests
import json

from lxml import html
from extract_data import Scraper
from spiders_shared_code.footlocker_variants import FootlockerVariants


class FootlockerScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.footlocker.com/product/<product-name>"
    REVIEW_URL = "http://footlocker.ugc.bazaarvoice.com/8001/{0}/reviews.djs?format=embeddedhtml"
    IMAGE_URLS = "http://images.footlocker.com/is/image/EBFL2/{sku}?req=set,json&handler=s7ViewResponse"

    def __init__(self, **kwargs):  # **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.product_json = None
        self.model_json = None
        self.review_json = None
        self.review_list = None
        self.is_review_checked = False
        self.fv = FootlockerVariants()
        self.image_urls_json = None

        self._set_proxy()

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://www.footlocker.com/product/.*?$", self.product_page_url)
        return not not m

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')

        if itemtype:
            if itemtype[1] != "product":
                return True

        self._extract_product_json()
        self.fv.setupCH(self.tree_html)

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_product_json(self):
        self.product_json = self.tree_html.xpath('//script[@type="application/ld+json"]')
        sku = self._sku()

        if self.product_json:
            self.product_json = json.loads(self.product_json[0].text_content(), strict=False)
        try:
            response = requests.get(self.IMAGE_URLS.format(sku=sku))
            if response.ok:
                self.image_urls_json = json.loads(self._find_between(response.text, 's7ViewResponse(', ',"")'))
        except:
            pass

        self.model_json = self._find_between(html.tostring(self.tree_html), 'var model = ', '};')
        try:
            if self.model_json:
                self.model_json = json.loads(self.model_json + '}')
        except:
            return

    def _product_id(self):
        product_id = self.tree_html.xpath("//span[@id='productSKU']/text()")
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
        return self.product_json['model']

    def _description(self):
        short_description = self.tree_html.xpath("//div[@id='pdp_description']//p/text()")
        return short_description[0] if short_description else None

    def _long_description(self):
        long_description = self.tree_html.xpath("//div[@id='pdp_description']//ul")
        if long_description:
            long_description = html.tostring(long_description[0])

        return self._clean_text(long_description)

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_url_list = []
        item_list = []
        image_url_temp = "http://images.footlocker.com/is/image/{item}?fit=constrain,1&wid=465&hei=324&fmt=jpg"

        image_urls = self.image_urls_json['set']['item']

        for image_item in image_urls:
            item_list.append(image_item['i']['n'])

        for item in item_list:
            image_url_list.append(image_url_temp.format(item=item))

        return image_url_list

    def _image_count(self):
        img_urls = self._image_urls()
        if img_urls:
            image_count = len(img_urls)

        return image_count

    def _variants(self):
        return self.fv._variants(self.model_json, self._image_urls())

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

        return average_rating

    def _review_count(self):
        self._reviews()

        if not self.review_json:
            return 0

        return int(self.review_json["jsonData"]["attributes"]["numReviews"])

    def _reviews(self):
        if self.is_review_checked:
            return self.review_list

        self.is_review_checked = True

        h = {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)
        contents = s.get(self.REVIEW_URL.format(self._model()), headers=h, timeout=5).text

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

    def _price_amount(self):
        price_amount = 0
        if self.product_json.get('offers', {}):
            price_amount = self.product_json['offers']['price']

        return price_amount

    def _price(self):
        price_amount = self._price_amount()
        return '$' + str(price_amount) if price_amount else None

    def _price_currency(self):
        currency = None

        if self.product_json.get('offers', {}):
            currency = self.product_json['offers']['priceCurrency']

        return currency if currency else "USD"

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
    def _brand(self):
        return self.product_json['brand']

    def _sku(self):
        return self._product_id()

    def _clean_text(self, text):
        return re.sub("[\r\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id": _product_id, \
 \
        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name, \
        "product_title": _product_title, \
        "model": _model, \
        "sku": _sku, \
        "description": _description, \
        "long_description": _long_description, \
        "variants": _variants, \
 \
        # CONTAINER : PAGE_ATTRIBUTES
        "image_count": _image_count, \
        "image_urls": _image_urls, \
 \
        # CONTAINER : REVIEWS
        "review_count": _review_count, \
        "average_review": _average_review, \
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
 \
        # CONTAINER : CLASSIFICATION
        "brand": _brand, \
        }
