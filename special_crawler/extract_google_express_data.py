#!/usr/bin/python

import re
import json
import traceback
from extract_data import Scraper
from lxml import html
from product_ranking.guess_brand import guess_brand_from_first_words
from spiders_shared_code.google_express_variants import GoogleExpressVariants


def catch_list_index_exception(func):
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except (IndexError, TypeError):
            print(
                '[WARNING] Can not retrieve value for `{}`'.format(func.__name__)
            )
    return wrapper

def get_item(data, paths):
    """
    CON-45925, sometimes product json has different sturcture
    in this case please update `paths` value in target function
    :param data: product json data
    :param paths: list of lists
    :return: value or raise IndexError
    """
    for path in paths:
        tmp_data = data[:]
        try:
            for index in path:
                tmp_data = tmp_data[index]
            return tmp_data
        except (IndexError, TypeError):
            continue
    raise IndexError()


class GoogleExpressScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://express.google.com/*"

    ADDITIONAL_DATA = "https://express.google.com/_/data?ds.extension=142508757&_egch=1&_reqid=48107&rt=j"

    def __init__(self, **kwargs):  # **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)
        self.reviews_checked = False
        self.product_json = []
        self.additional_data = []
        self.gv = GoogleExpressVariants()

    def check_url_format(self):
        m = re.match(r"^https?://express.google.com/.*?", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        product_json = re.search(r"hash: '4', data:function\(\)\{return(.*?)\}\}\);</script>",
                                 self.page_raw_text, re.DOTALL)
        try:
            self.product_json = json.loads(product_json.group(1))
            self._get_variants_data()
        except:
            print 'Error parsing product json: {}'.format(traceback.format_exc())
            return True

        return False

    def _get_variants_data(self):
        prices = self._get_product_prices()
        self.additional_data = self._get_additional_data()
        self.gv.setupCH(self.product_json, prices=prices)

    def _get_additional_data(self):
        url = re.search(r'(/product/.*)', self.product_page_url)
        if url:
            data = 'f.req=%5B%5B%5B142508757%2C%5B%7B%22142508757%22%3A%5Bnull%2C%22moar%20plz%22%2Cnull%2Cnull' \
                   '%2C1%2Cnull%2C%22{url}%22%2Cnull%2C%22https%3A%2F%2Fexpress.google.com%2F%22%5D%7D%5D%2Cnull' \
                   '%2Cnull%2C0%5D%5D%5D&'.format(url=url.group(1).replace('/', '%2F'))
            headers = {
                'content-type': 'application/x-www-form-urlencoded;charset=UTF-8'
            }
            req = self._request(
                self.ADDITIONAL_DATA,
                verb='post',
                headers=headers,
                data=data
            )
            if req.status_code == 200:
                try:
                    raw_data = re.search(r'(\[.*\])', req.text, re.DOTALL)
                    if raw_data:
                        additional_data = json.loads(raw_data.group(1))
                        return additional_data
                except ValueError:
                    print('Error parsing additional_data json: {}'.format(traceback.format_exc()))

    @catch_list_index_exception
    def _get_product_prices(self):
        prices = []
        if self.product_json[1][1][1][0][48][3]:
            for data in self.product_json[1][1][1][0][48][3][0][0][1]:
                r = self._request('https://express.google.com/' + data[4])
                product_data = re.search("hash: '4', data:function\(\){return(.*?)}}\);</script>", r.text, re.DOTALL)
                if product_data:
                    json_product_data = json.loads(product_data.group(1))
                    try:
                        if json_product_data[1][0][1][0][48][4][1]:
                            prices.append(json_product_data[1][1][1][0][48][4][1])
                    except IndexError:
                        if json_product_data[1][1][1][0][48][4]:
                            prices.append(json_product_data[1][1][1][0][48][4][1])
                        else:
                            prices.append(json_product_data[1][1][1][0][48][11][2][1])
                else:
                    if self.product_json[1][1][1][0][48][4]:
                        prices.append(json_product_data[1][1][48][4][1])
                    else:
                        prices.append(self.product_json[1][1][48][11][2][1])
        return prices

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_id(self):
        product_id = re.search(r'/product/(.*)\??', self.product_page_url)
        return product_id.group(1) if product_id else None

    @catch_list_index_exception
    def _brand(self):
        try:
            brand = re.search('Brand: (.*)', self.product_json[1][1][12][1][3][1][0][1], re.DOTALL).group(1)
        except IndexError:
            brand = guess_brand_from_first_words(self._product_name())
        return brand if brand else None

    @catch_list_index_exception
    def _product_name(self):
        paths = [
            [18, 0, 1],
            [1, 1, 1, 0, 17, 0, 1],
            [1, 0, 1, 0, 17, 0, 1]
        ]
        return get_item(self.product_json, paths)

    @catch_list_index_exception
    def _description(self):
        paths = [
            [1, 1, 1, 2, 12, 1, 0, 1, 0, 1],
            [1, 1, 1, 1, 12, 1, 0, 1, 0, 1],
            [1, 0, 1, 2, 12, 1, 0, 1, 0, 1],
            [1, 0, 1, 1, 12, 1, 0, 1, 0, 1]
        ]
        return get_item(self.product_json, paths)

    @catch_list_index_exception
    def _features(self):
        features = []
        for feature_pair in self.additional_data[0][0][2].itervalues().next()[1][0][1][1][13][1][0][1]:
            features.append('{}: {}'.format(feature_pair[0], feature_pair[1]))
        return features if features else None

    @catch_list_index_exception
    def _variants(self):
        return self.gv._variants()

    def _primary_seller(self):
        seller = re.search(r'Sold by (.*?)",', json.dumps(self.product_json))
        if seller:
            return seller.group(1)

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    @catch_list_index_exception
    def _image_urls(self):
        paths = [
            [1, 1, 1, 0, 48, 1, 0],
            [1, 0, 1, 0, 48, 1, 0]
        ]
        return get_item(self.product_json, paths)

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################
    @catch_list_index_exception
    def _average_review(self):
        paths = [
            [1, 1, 1, 0, 48, 0, 1],
            [1, 0, 1, 0, 48, 0, 1]
        ]
        return get_item(self.product_json, paths)

    @catch_list_index_exception
    def _review_count(self):
        paths = [
            [1, 1, 1, 0, 48, 0, 2],
            [1, 0, 1, 0, 48, 0, 2]
        ]
        review_data = get_item(self.product_json, paths)
        if review_data:
            count = re.search('\d+(?:[,.]\d+)?', review_data)
            return int(re.sub('[^\d]', '', count.group())) if count else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    @catch_list_index_exception
    def _price(self):
        paths = [
            [1, 1, 1, 0, 48, 11, 2, 1],
            [1, 0, 1, 0, 48, 4, 1]
        ]
        return get_item(self.product_json, paths)

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    @catch_list_index_exception
    def _site_online_out_of_stock(self):
        paths = [
            [1, 1, 1, 0, 48, 11, 0, 0, 0, 0, 3],
            [1, 0, 1, 0, 48, 7, 0, 0, 0, 3]
        ]
        return int(get_item(self.product_json, paths) == "SOLD OUT")

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    @catch_list_index_exception
    def _categories(self):
        categories = []
        try:
            category_list = self.product_json[22][0]
        except:
            category_list = self.product_json[1][1][1][0][17][0][3].split('>')
        for cat in category_list:
            if type(cat) == list:
                cat = cat[0]
            categories.append(cat.strip())
        return categories

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {

        # CONTAINER : PRODUCT_INFO
        "product_id": _product_id,
        "brand": _brand,
        "product_name" : _product_name,
        "description": _description,
        "features": _features,
        "variants": _variants,
        "primary_seller": _primary_seller,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,

        }
