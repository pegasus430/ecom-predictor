#!/usr/bin/python

import urllib
import re
import json
import copy
import os.path
import requests
from lxml import html

from extract_data import Scraper
from spiders_shared_code.rakuten_variants import RakutenVariants


class RakutenScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################
    INVALID_URL_MESSAGE = "Expected URL format is http://www.rakuten.com/prod/.*$"

    feature_count = None
    features = None
    video_urls = None
    video_count = 0
    pdf_urls = None
    pdf_count = None
    wc_content = None
    wc_video = None
    wc_pdf = None
    wc_prodtour = None
    wc_360 = None
    max_score = None
    min_score = None
    review_count = None
    average_review = None
    reviews = None
    product_json = None

    def __init__(self, **kwargs):  # **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)
        self.product_json = None

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
        True if valid, False otherwise
        """
        m = re.match(r"^http://www.rakuten.com/.*$", self.product_page_url)
        return not not m

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """
        try:
            if not self.tree_html.xpath('//div[@itemtype="http://schema.org/Product"]'):
                raise Exception()
        except Exception:
            return True

        self._extract_product_json()

        return False

    def _extract_product_json(self):

        if self.tree_html.xpath("//script[contains(text(), 'dataLayer = [{')]/text()"):
            product_json = self.tree_html.xpath("//script[contains(text(), 'dataLayer = [{')]/text()")
            product_json = product_json[0].strip() if product_json else ''
            start_index = product_json.find("dataLayer = [") + len("dataLayer = [")
            end_index = product_json.find("];")
            product_json = product_json[start_index:end_index].strip()
            product_json = json.loads(product_json)
        else:
            product_json = None

        self.product_json = product_json

        return self.product_json

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _canonical_link(self):
        return self.tree_html.xpath('//link[@rel="canonical"]/@href')[0]

    def _url(self):
        return self.product_page_url

    def _event(self):
        return None

    def _product_id(self):
        if 'productSku' in self.product_json:
            prod_id = self.product_json['productSku']
        else:
            prod_id = re.search('/([a-zA-Z0-9])+\.html', self.product_page_url).group(1)
        return prod_id

    def _site_id(self):
        return None

    def _status(self):
        return "success"

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        if 'productName' in self.product_json:
            return self.product_json['productName']
        return self.tree_html.xpath('//h1[@id="product-title-heading"]//text()')[0]

    def _product_title(self):
        return self.tree_html.xpath('//meta[@itemprop="name"]/@content')[0]

    def _title_seo(self):
        return self.tree_html.xpath("//meta[@property='og:title']/@content")[0].strip()

    def _model(self):
        return None

    def _upc(self):
        if 'productUpc' in self.product_json:
            return self.product_json['productUpc']
        return None

    def _features(self):
        features_td_list = self.tree_html.xpath('//table[contains(@class, "tab-table")]//tr')
        features_list = []

        for index, val in enumerate(features_td_list):
            if features_td_list[index - 1].xpath(".//th//text()") \
                    and features_td_list[index - 1].xpath(".//td//text()"):
                features_list.append(features_td_list[index - 1].xpath(".//th//text()")[0].strip() +
                                     " : " + features_td_list[index].xpath(".//td//text()")[0].strip())

        if features_list:
            return features_list

        return None

    def _feature_count(self):
        if self._features():
            return len(self._features())

        return None

    def _model_meta(self):
        return None

    def _description(self):
        short_description = ''
        if len(self.tree_html.xpath('//div[@itemprop="description"]')):
            short_description = self.tree_html.xpath('//div[@itemprop="description"]')[0].text_content()

        if short_description:
            return short_description

        return None

    def _long_description(self):

        return None

    def _swatches(self):
        swatches = []

        for img in self.tree_html.xpath('//div[contains(@class, "sku_variant")]/ul/li/a/img'):
            swatch = {
                'color' : img.get('title'),
                'hero' : 1,
                'hero_image' : img.get('src')
            }
            swatches.append(swatch)

        if swatches:
            return

    def _variants(self):
        variants = []

        first_sku_variant = True

        for sku_variant in self.tree_html.xpath('//div[contains(@class, "sku_variant")]'):
            variants = []

            for option in sku_variant.xpath('ul/li'):
                if 'product_sku_Overlay_ColorSwatch' in sku_variant.get('class'):
                    v = {
                        'selected' : False,
                        'properties' : {
                            'color' : option.xpath('a/img/@title')[0]
                        }
                    }

                    if option.get('class') and 'selected' in option.get('class'):
                        v['selected'] = True

                else:
                    custom_label = sku_variant.xpath('a[@class="customLabel"]/text()')[0]
                    selected_value = sku_variant.xpath('a[@class="customLabel"]/span[contains(@class,"select")]/text()')[0]

                    value = option.xpath('a/text()')[0]

                    v = {
                        'selected' : selected_value == value,
                        'properties' : {
                            custom_label : value
                        }
                    }

                if not first_sku_variant:
                    for variant in original_variants:
                        variant_copy = copy.deepcopy(variant)
                        variant_copy['properties'].update(v['properties'])
                        if not v['selected']:
                            variant_copy['selected'] = False
                        variants.append(variant_copy)

                else:
                    variants.append(v)

            original_variants = copy.deepcopy(variants)
            first_sku_variant = False

        if variants:
            return variants

    def _no_longer_available(self):
        return 0
    #
    # ##########################################
    # ############### CONTAINER : PAGE_ATTRIBUTES
    # ##########################################
    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//ul[@id="productlist"]//img/@src')
        if image_urls:
            return map(lambda u: u.split(';')[0], image_urls)

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    def _video_urls(self):
        self.video_count = 0
        return None

    def _video_count(self):
        if self._video_urls() is None:
            return 0
        return self.video_count

    def _pdf_urls(self):
        return None

    def _pdf_count(self):
        urls = self._pdf_urls()
        if urls:
            return len(urls)
        return 0

    def _webcollage(self):
        return None

    def _htags(self):
        htags_dict = {}
        # add h1 tags text to the list corresponding to the "h1" key in the dict
        htags_dict["h1"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h1//text()[normalize-space()!='']"))
        # add h2 tags text to the list corresponding to the "h2" key in the dict
        htags_dict["h2"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h2//text()[normalize-space()!='']"))
        return htags_dict

    def _keywords(self):
        return self.tree_html.xpath("//meta[@name='keywords']/@content")[0]

    # ##########################################
    # ############### CONTAINER : REVIEWS
    # ##########################################
    def _average_review(self):
        if self._review_count() > 0:
            return float(self.tree_html.xpath('//meta[@itemprop="ratingValue"]/@content')[0])

        return None

    def _review_count(self):
        if not self.tree_html.xpath('//span[@itemprop="reviewCount"]'):
            return 0

        return int(self.tree_html.xpath('//span[@itemprop="reviewCount"]//text()')[0].replace(',', ''))

    def _max_review(self):
        if self._review_count() == 0:
            return None

        reviews = self._reviews()

        for review in reviews:
            if review[1] > 0:
                return review[0]

    def _min_review(self):
        if self._review_count() == 0:
            return None

        reviews = self._reviews()
        reviews = reviews[::-1]

        for review in reviews:
            if review[1] > 0:
                return review[0]

    def _reviews(self):
        ratings = self.tree_html.xpath('//div[@class="cust-review-block-tall"]/div[@id="ratings"]/div[@class="rating-indicator"]/text()')
        reviews = [[5-stars_num, int(ratings[stars_num])] for stars_num in range(0, 5)]

        return reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        meta_price = self.tree_html.xpath('//div[@class="main-price"]//span[@class="text-primary"]//text()')
        if meta_price:
            return meta_price[0].strip()
        else:
            return None

    def _price_amount(self):
        price = self._price()
        price = price.replace(",", "")
        price_amount = re.findall(r"[\d\.]+", price)[0]
        return float(price_amount)

    def _price_currency(self):
        if 'currency' in self.product_json:
            return self.product_json['currency']

    def _in_stores(self):
        arr = self.tree_html.xpath('//div[@id="product-actions"]//strong[contains(@class,"text-success")]//text()')
        if "in stock" in " ".join(arr).lower():
            return 1
        return 0

    def _marketplace(self):
        return 0

    def _marketplace_sellers(self):
        return None

    def _marketplace_lowest_price(self):
        return None

    def _marketplace_out_of_stock(self):
        """Extracts info on whether currently unavailable from any marketplace seller - binary
        Uses functions that work on both old page design and new design.
        Will choose whichever gives results.
        Returns:
            1/0
        """
        return None

    def _site_online(self):
        # site_online: the item is sold by the site (e.g. "sold by Amazon") and delivered directly, without a physical store.
        return 1


    def _site_online_out_of_stock(self):
        #  site_online_out_of_stock - currently unavailable from the site - binary
        if self.product_json['productOutOfStock'] == u'True':
            return 1
        return 0

    def _in_stores_out_of_stock(self):
        '''in_stores_out_of_stock - currently unavailable for pickup from a physical store - binary
        (null should be used for items that can not be ordered online and the availability may depend on location of the store)
        '''
        if self._in_stores() == 0:
            return None
        return 0

   ##########################################
   ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.tree_html.xpath("//div[@class='product-breadcrumbs']/ul/li/a/text()")

        if categories:
            return categories

        return None

    def _category_name(self):
        return self._categories()[-1]

    def _brand(self):
        return None

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
        "event" : _event, \
        "product_id" : _product_id, \
        "site_id" : _site_id, \
        "status" : _status, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "model" : _model, \
        "upc" : _upc,\
        "model_meta" : _model_meta, \
        "description" : _description, \
        "long_description" : _long_description, \
        "swatches" : _swatches, \
        "variants": _variants, \
        "no_longer_available" : _no_longer_available, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count" : _image_count,\
        "image_urls" : _image_urls, \
        "htags" : _htags, \
        "keywords" : _keywords, \
        "canonical_link": _canonical_link, \

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
        "in_stores" : _in_stores, \
        "marketplace": _marketplace, \
        "marketplace_sellers" : _marketplace_sellers, \
        "marketplace_lowest_price" : _marketplace_lowest_price, \
        "marketplace_out_of_stock" : _marketplace_out_of_stock, \
        "site_online" : _site_online, \
        "site_online_out_of_stock" : _site_online_out_of_stock, \
        "in_stores_out_of_stock" : _in_stores_out_of_stock, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "category_name" : _category_name, \
        "brand" : _brand, \

        "loaded_in_seconds" : None, \
        }
    #
    # # special data that can't be extracted from the product page
    # # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = { \
        # CONTAINER : PRODUCT_INFO
        "features" : _features, \
        "feature_count" : _feature_count, \

        # CONTAINER : PAGE_ATTRIBUTES
        "mobile_image_same" : _mobile_image_same, \
        "webcollage" : _webcollage, \
        "pdf_urls" : _pdf_urls, \
        "pdf_count" : _pdf_count, \
        "video_urls" : _video_urls, \
        "video_count" : _video_count, \
        }
