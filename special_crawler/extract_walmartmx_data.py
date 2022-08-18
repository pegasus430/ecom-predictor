#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import lxml
import requests
import json

from lxml import html
from extract_data import Scraper
from urlparse import urljoin

is_empty = lambda x, y="": x[0] if x else y

class WalmartMXScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www\.walmart\.com\.mx/[product-categories]/[product-name]-[product-id]"


    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.product_detail_json = None
        self.product_detail_json_checked = False

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^https?://www\.walmart\.com\.mx/[\w\d/-]+[-_][\w\d]+/?(\?.*)?$", self.product_page_url, re.U)
        return bool(m)

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """
        try:
            if self.tree_html.xpath("//meta[@itemtype='http://schema.org/Product']"):
                raise Exception()
        except Exception:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _canonical_link(self):
        return self.product_page_url

    def _product_id(self):
        if re.match('https://www.walmart.com.mx/super', self._url()):
            product_id =  self.tree_html.xpath("//*[@itemprop='mpn']/text()")
            return product_id[0] if product_id else None

        return re.match('.*[-_]([\w\d]+)$', self._url()).group(1)

    def _sku(self):
        return None

    def _url(self):
        return self.product_page_url

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _load_product_detail_json(self):
        if not self.product_detail_json_checked:
            self.product_detail_json_checked = True

            self.product_detail_json = json.loads( re.match('[^{]*({.*})', self.load_page_from_url_with_number_of_retries('https://www.walmart.com.mx/WebControls/hlGetProductDetail.ashx?upc=' + self._product_id())).group(1))['c']['facets']['_' + self._product_id()]

        return self.product_detail_json

    def _product_name(self):
        self._load_product_detail_json()

        if self.product_detail_json:
            return self.product_detail_json['n']

        return self.tree_html.xpath('//*[@id="lblTitle"]/text()')[0].strip()

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _upc(self):
        return self._product_id()

    def _model(self):
        self._load_product_detail_json()

        if self.product_detail_json:
            for data in self.product_detail_json['data']:
                if data['n'] == 'Modelo':
                    return data['v']

        model = self.tree_html.xpath("//*[@itemprop='model']/@content")
        return model[0] if model else None

    def _features(self):
        self._load_product_detail_json()

        features = []

        if self.product_detail_json:
            for data in self.product_detail_json['data']:
                features.append(data['n'] + ': ' + data['v'])

        if features:
            return features

        keys = self.tree_html.xpath('//*[@id="lblCarac"]/div/div[1]/text()')
        values = self.tree_html.xpath('//*[@id="lblCarac"]/div/div[2]/text()')
        features_paired = zip(keys,values)
        return [ "%s: %s" % (x[0], x[1]) for x in  features_paired] if features_paired else None

    def _feature_count(self):
        features = self._features()
        return len(features) if features else 0

    def _description(self):
        self._load_product_detail_json()

        if self.product_detail_json:
            return self.product_detail_json['d']

        description = self.tree_html.xpath(
            '//*[@itemprop="description"]/text()') or self.tree_html.xpath(
                '//*[@id="productoDescripcionTexto"]//text()')
        return ' '.join(map(lambda x: x.strip(), description))

    def _long_description(self):
        long_description = self.tree_html.xpath(
            '//*[@itemprop="description"]//text()')
        return ' '.join(map(lambda x: x.strip(), long_description)) or \
            self._description()

    def _ingredients(self):
        ingredients = self.tree_html.xpath('//*[@id="lblIngredientes"]/text()')[0]
        if u'Información no disponible' in ingredients:
            return None
        return map((lambda x: x.group(1).strip().capitalize()),re.finditer(r"(.*?\s*(\[.*?\]\s*)?(\(.*?\)\s*)?)(,|\.| y )", ingredients))

    def _ingredients_count(self):
        ingredients = self._ingredients()
        return len(ingredients) if ingredients else 0

    def _variants(self):
        return None

    def _rollback(self):
        return None

    def _no_longer_available(self):
        self._load_product_detail_json()

        if self.product_detail_json:
            return not self.product_detail_json['av'] == '1'

        return False if self.tree_html.xpath('//link[@itemprop="availability" and @href="http://schema.org/InStock"]') else True

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _mobile_image_same(self):
        pass

    def _image_urls(self):
        # There is 1 to 3 images on this website.
        # It always will include 3 images URL on the page but sometimes URL 2 and 3 will not work and are hidden.
        # To see if the image is valid we will have to load it with, causing a penalty in execution time.
        if re.match('https://www.walmart.com.mx/super', self._url()):
            results = []
            images = self.tree_html.xpath('//*[@itemprop="image"]/@src |'
                                          '//*[@class="imgChange"]/@src |'
                                          '//*[contains(@id,"imgDetalle")]/@src')

            images = list(set(map((lambda x: urljoin(self.product_page_url, x)),
                                  images)))

            for image_url in images:
                http_head_response = requests.head(image_url)
                if 'img_large' in image_url and http_head_response.status_code == 200:
                    results.append(image_url)

            return results

        image_urls = ['https://www.walmart.com.mx/images/products/img_large/' + self._product_id() + 'l.jpg']

        for i in range(1,4):
            image_url = 'https://www.walmart.com.mx/images/products/img_large/' + self._product_id() + '-' + str(i) + 'l.jpg'
            if requests.get(image_url).headers['content-type'] == 'image/jpeg':
                image_urls.append(image_url)

        return image_urls

    def _image_count(self):
        images = self._image_urls()
        return len(images) if images else 0

    def _video_urls(self):
        return None

    def _video_count(self):
        return 0

    # return dictionary with one element containing the PDF
    def _pdf_urls(self):
        return None

    def _pdf_count(self):
        return 0

    def _wc_emc(self):
        return 0

    def _wc_prodtour(self):
        return 0

    def _wc_360(self):
        return 0

    def _wc_video(self):
        return 0

    def _wc_pdf(self):
        return 0

    def _webcollage(self):
        if self._wc_360() == 1 or self._wc_prodtour() == 1 or self._wc_pdf() == 1 or self._wc_emc() == 1 or self._wc_360():
            return 1

        return 0

    def _htags(self):
        htags_dict = {}
        htags_dict["h1"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h1//text()[normalize-space()!='']"))
        htags_dict["h2"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h2//text()[normalize-space()!='']"))

        return htags_dict

    def _keywords(self):
        if re.match('https://www.walmart.com.mx/super', self._url()):
            keywords = self.tree_html.xpath('//meta[@name="keywords"]/@content')
        else:
            keywords = self.tree_html.xpath('//meta[@name="Keywords"]/@content')

        return keywords[0].strip() if keywords else None

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        return None

    def _review_count(self):
        return 0

    def _max_review(self):
        return None

    def _min_review(self):
        return None

    def _reviews(self):
        return None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        self._load_product_detail_json()

        if self.product_detail_json:
            return '$' + self.product_detail_json['p']

        try:
            return self.tree_html.xpath("//*[@itemprop='price']/text()|"
                                        "//*[@itemprop='price']/@content")[0]
        except:
            return None

    def _price_amount(self):
        self._load_product_detail_json()

        if self.product_detail_json:
            return float(self.product_detail_json['p'])

        return float(self.tree_html.xpath("//*[@itemprop='price']/text()|"
                                    "//*[@itemprop='price']/@content")[0][1:])

    def _price_currency(self):
        try:
            return self.tree_html.xpath("//meta[@itemprop='priceCurrency']/@content")[0]
        except:
            return 'MXN'


    def _site_online(self):
        return 1

    def _in_stores(self):
        if "sorry, this item is currently not available in stores." in html.tostring(self.tree_html).lower():
            return 0

        return 1

    def _site_online_out_of_stock(self):
        return 1 if self._no_longer_available() else 0

    def _marketplace_sellers(self):
        return None

    def _marketplace_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################    

    def _categories(self):
        if re.match('https://www.walmart.com.mx/super', self._url()):
            return self.tree_html.xpath("//*[@id='breadcrumb']//a/text()")

        return self._url().split('/')[3:-1]

    def _category_name(self):
        return self._categories()[-1]

    def _brand(self):
        manufacturer = self.tree_html.xpath("//*[@itemprop='manufacturer']/@content")
        return manufacturer[0] if manufacturer else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    def _clean_text(self, text):
        return re.sub("&nbsp;", " ", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "url" : _url, \
        "product_id" : _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "model" : _model, \
        "features" : _features, \
        "feature_count" : _feature_count, \
        "description" : _description, \
        "long_description" : _long_description, \
        "ingredients": _ingredients, \
        "ingredient_count": _ingredients_count,
        "variants": _variants,
        "rollback": _rollback,
        "no_longer_available": _no_longer_available,
        "upc": _upc,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count" : _image_count,\
        "image_urls" : _image_urls, \
        "video_count" : _video_count, \
        "video_urls" : _video_urls, \
        "pdf_count" : _pdf_count, \
        "pdf_urls" : _pdf_urls, \
        "webcollage" : _webcollage, \
        "wc_360": _wc_360, \
        "wc_emc": _wc_emc, \
        "wc_pdf": _wc_pdf, \
        "wc_prodtour": _wc_prodtour, \
        "wc_video": _wc_video, \
        "htags" : _htags, \
        "keywords" : _keywords, \
        "canonical_link": _canonical_link,

        # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \
        "max_review" : _max_review, \
        "min_review" : _min_review, \
        "reviews" : _reviews, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "price_amount" : _price_amount, \
        "price_currency" : _price_currency, \
        "marketplace" : _marketplace, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "in_stores" : _in_stores, \
        "marketplace_sellers" : _marketplace_sellers, \
        "marketplace_out_of_stock": _marketplace_out_of_stock, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "category_name" : _category_name, \
        "brand" : _brand, \
        }

    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = { \
        "mobile_image_same" : _mobile_image_same, \
    }
