#!/usr/bin/python

import re
import json
import requests

from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words


class BjsScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.bjs.com/*"

    REVIEW_URL = "https://readservices-b2c.powerreviews.com/m/9794/l/en_US/product/P_{}/reviews?"

    PRODUCT_URL = "https://api.bjs.com/digital/live/api/v1.0/pdp/10201?productId={product_id}&pageName=PDP&clubId=0096"

    IMAGE_URLS = "https://richmedia.channeladvisor.com/ViewerDelivery/productXmlService?" \
                 "profileid={pid}&itemid={item_id}&viewerid=870"

    VIDEO_URL = "http://ws.cnetcontent.com/d0e726d2/script/e7f41f8895?mf={brand}&pn={model}&" \
                "upcean=&lang=en&market=US&host=www.bjs.com&nld=1"

    WEBCOLLAGE_POWER_PAGE = "https://scontent.webcollage.net/bjs/power-page?ird=true&channel-product-id={}"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.image_urls = None
        self.checked_image_urls = False
        self.video_urls = []
        self.video_checked = False
        self.product_data = None

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries(use_session=True, save_session=True)

    def _pre_scrape(self):
        self._extract_product_json()
        if self.product_data:
            pid = self.product_data.get('bjsitems', [{}])[0].get('articleId')
            if pid:
                self._extract_webcollage_contents(product_id=pid)

    def not_a_product(self):
        if not self.product_data:
            return True

    def _get_profile_id(self):
        pid = re.search('profileId=(\d+)', self.page_raw_text)
        return pid.group(1) if pid else None

    def _extract_product_json(self):
        resp = self._request(
            self.PRODUCT_URL.format(product_id=self._product_id()),
            session=self.session
        )
        if resp.status_code == 200:
            self.product_data = resp.json()

    def _review_id(self):
        return self.product_data.get('bjsitems', [{}])[0].get('partNumber')

    def _extract_auth_key(self):
        api_url = re.search(r'src=(main.*?)>', self.page_raw_text)
        if api_url:
            resp = self._request(
                'https://www.bjs.com/{}'.format(api_url.group(1)),
                session=self.session,
            )
            if resp.status_code == 200:
                api_key = re.search(r'apiKey:\"(.*?)\"', resp.text)
                return api_key.group(1) if api_key else None

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _product_id(self):
        product_id = re.search(r'\d{4,}', self.product_page_url)
        return product_id.group() if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.product_data.get('description', {}).get('name')

    def _description(self):
        description_data = self.product_data.get('description', {}).get('longDescription', '')
        description = re.search(r'(.*?)\n?<BR>', description_data, re.DOTALL)
        return description.group(1) if description else None

    def _features(self):
        description_data = self.product_data.get('description', {}).get('longDescription', '')
        features = re.findall(r'LI>(.*?)\n?<', description_data, re.DOTALL)
        return features if features else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _canonical_link(self):
        return self.product_page_url.split('?')[0]

    def _image_urls(self):
        if self.checked_image_urls:
            return self.image_urls

        self.checked_image_urls = True
        pid = self._get_profile_id()
        item_id = self.product_data.get('productImages', {}).get('imageName')
        if pid and item_id is not None:
            resp = self._request(
                self.IMAGE_URLS.format(
                    pid=pid,
                    item_id=item_id
                ),
                session=self.session
            )
            if resp.status_code == 200:
                self.image_urls = [x.replace('&amp;', '&') for x in re.findall(r'path=\"(.*?)\"', resp.text)]
        return self.image_urls

    def _video_urls(self):
        if self.video_checked:
            return self.video_urls

        self.video_checked = True
        brand = self._brand()
        model = self._model()
        data = self._request(
            self.VIDEO_URL.format(brand=brand, model=model).replace('#', '%23'),
            session=self.session
        )
        if data:
            video_list = re.findall('ndata-video-url=\\\\"(.*?)\\\\', data.content)
            for video in video_list:
                self.video_urls.append(video)
            if not self.video_urls:
                video_list = re.findall('ndata-url=\\\\"(.*?)\\\\"', data.content)
                for video in video_list:
                    self.video_urls.append(video)

        if self.wc_videos:
            for vide_url in self.wc_videos:
                if vide_url not in self.video_urls:
                    self.video_urls.append(vide_url)

        return self.video_urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.product_data.get('bjsClubProduct', [{}])[0].get('clubItemStandardPrice', {})
        if not price:
            price = self.product_data.get('minimumItemPrice', {})
        return price.get('amount')

    def _in_stores(self):
        return int(self.product_data.get('bjsClubProduct', [{}])[0].get('itemAvailableInClub', 'N') == 'Y')

    def _site_online(self):
        return int(self.product_data.get('bjsClubProduct', [{}])[0].get('itemAvailableOnline', 'N') == 'Y')

    def _site_online_out_of_stock(self):
        if self.tree_html.xpath('//div[contains(@class, "outOfStockOnline")]'):
            return 1
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        return guess_brand_from_first_words(self._product_name())

    def _categories(self):
        categories = []
        for x in range(self.product_data.get('breadCrumbDetail', {}).get('Levels', 0)):
            category = self.product_data.get('breadCrumbDetail', {}).get('Level{}'.format(x+1))
            if '||' in category:
                categories.append(category.split('||')[-1])

        return categories if categories else None

    def _model(self):
        return self._saerch_attribute('Model Number', self.product_data)

    def _upc(self):
        return self._saerch_attribute('upc', self.product_data)

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    @staticmethod
    def _saerch_attribute(attribute_name, data):
        for attr in data.get('descriptiveAttributes'):
            if attr.get('name') == attribute_name:
                return attr.get('attributeValueDataBeans', [{}])[0].get('value')

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "description": _description,
        "features": _features,

        # CONTAINER : PAGE_ATTRIBUTES
        "canonical_link": _canonical_link,
        "image_urls": _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "site_online": _site_online,
        "in_stores": _in_stores,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        "upc": _upc,
        "model": _model,
        }
