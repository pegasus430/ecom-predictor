#!/usr/bin/python

import re
import json
import traceback
import requests

from lxml import html
from extract_data import Scraper, deep_search
from spiders_shared_code.drizly_variants import DrizlyVariants


class DrizlyScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.drizly.com/<product-name>/<product id>"

    REVIEWS_URL = 'https://drizly.com/product/reviews?format=json&count={}&catalog_item_id={}'

    SET_ZIP_URL = 'https://drizly.com/location/async_create'

    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.98 Safari/537.36"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.product_json = None

    def check_url_format(self):
        m = re.match(r"^https?://drizly.com/.+/p\d+", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        self._extract_product_json()
        self._extract_review_json()

        if self.product_json.get('props') is not None:
            self.dv = DrizlyVariants()
            self.dv.setupCH(self.tree_html)
            return False
        return True

    def _extract_page_tree(self):
        with requests.session() as session:
            try:
                #get tokens
                resp = self._request(self.product_page_url, session=session)
                csrf, xpid = self._get_tokens(resp)
                data = "persist=false&address%5Baddress1%5D=undefined&address%5Bcity%5D=Reedsport&address%5B" \
                       "state%5D=OR&address%5Bzip%5D=97467&address%5Blatitude%5D=43.76918939999999&address%5B" \
                       "longitude%5D=-123.92878259999998&address%5Bcountry_code%5D=US&delivery_types=20"
                session.headers.update({
                    'x-csrf-token': csrf,
                    'x-newrelic-id': xpid,
                    'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'x-requested-with': 'XMLHttpRequest',
                })
                # set zip_code
                self._request(self.SET_ZIP_URL, session=session, verb='post', data=data)
                resp = self._request(self.product_page_url, session=session)
                if resp.status_code == 200:
                    self.page_raw_text = resp.text
                    self.tree_html = html.fromstring(self.page_raw_text)
            except Exception as e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', str(e))

    @staticmethod
    def _get_tokens(resp):
        csrf_token = re.search(r'(?<=name=\"csrf-token\").*content=\"(.*?)\"', resp.text)
        xpid = re.search(r'xpid:\"(.*?)\"', resp.text)
        if csrf_token and xpid:
            return csrf_token.group(1), xpid.group(1)
        else:
            raise ValueError('csrf_token or xpid not found')

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_product_json(self):
        self.product_json = self.tree_html.xpath('//div[@data-integration-name="redux-store"]/@data-payload')
        if self.product_json is not None:
            self.product_json = json.loads(self.product_json[0])

    def _extract_review_json(self):
        try:
            pId = re.search('\d+', self._product_id()).group()
            self.review_count = int(re.search('(\d+) reviews', html.tostring(self.tree_html)).group(1))
            self.average_review = round(float(self.tree_html.xpath('//span[@class="rating-average"]/text()')[0]), 1)
            self.review_json = self._request(self.REVIEWS_URL.format(self.review_count, pId)).json()
        except Exception as e:
            print traceback.format_exc()

            if self.lh:
                self.lh.add_list_log('errors', 'Error extracting reviews: {}'.format(e))

    def _product_id(self):
        return self.product_page_url.split('?')[0].split('/')[-1]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.product_json.get('props', {}).get('catalogItemName')

    def _description(self):
        desc_brand = None
        description = ''
        description_data = self.tree_html.xpath('//div[@class="product-entry"]/text()')
        if not description_data:
            desc_brand = self.tree_html.xpath("//*[contains(@class, 'ProductDescription')]/h2/text()")
            description_data = self.tree_html.xpath("//*[contains(@class, 'ProductDescription')]//p/text()")
        if desc_brand:
            description = desc_brand[0]
        if description_data:
            description += ' ' + description_data[0]
        return self._clean_text(description) if description else None

    def _long_description(self):
        long_description = ''
        long_descriptions = self.tree_html.xpath('//div[@class="text-widget"]/descendant::text()')
        for desc in long_descriptions:
            long_description += desc
        return self._clean_text(long_description) if long_description else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath("//div[contains(@class, 'ProductMeta__product-image')]//img/@src")
        return image_urls

    def _video_urls(self):
        video_list = []
        video_ids = re.findall('"videoID":"(.*?)"', html.tostring(self.tree_html))
        if video_ids:
            for video_id in video_ids:
                video_url = 'https://www.youtube.com/embed/{}'.format(video_id)
                video_list.append(video_url)
        else:
            video_urls = self.tree_html.xpath('//iframe/@src')
            for video_url in video_urls:
                if 'youtube.com' in video_url and video_url not in video_list:
                    video_list.append(video_url)
        return video_list if video_list else None

    def _variants(self):
        return self.dv._variants()

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        rating_by_star = []
        rating_value_list = []

        for review in self.review_json:
            rating_value_list.append(review['score'])

        for i in range(0, 5):
            rating_by_star.append([5-i, int(rating_value_list.count(5-i))])

        return rating_by_star

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        return self.product_json.get('props', {}).get('availabilityMap', {}).get('map', {})\
            .get(str(self.product_json.get('props', {}).get('selectedVariantId')), [{}])[0].get('price_raw')

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self.product_json.get('props', {}).get('availabilityMap', {}).get('map'):
            return 0
        return 1

    def _in_stores_out_of_stock(self):
        if self.product_json.get('props', {}).get('availabilityMap', {}).get('map'):
            return 0
        return 1

    def _primary_seller(self):
        primary_seller = deep_search('store_name', self.product_json)
        return primary_seller[0] if primary_seller else None

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//span[@property='name']/text()")
        return categories[1:] if categories else None

    def _brand(self):
        return self.product_json.get('props', {}).get('brand', {}).get('name')

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    def _clean_text(self, text):
        return re.sub("[\r\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "description": _description,
        "long_description": _long_description,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,
        "variants": _variants,

        # CONTAINER : REVIEWS
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,
        "primary_seller": _primary_seller,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand
        }
