#!/usr/bin/python
# -*- coding: utf-8 -*-

import re, json
from lxml import html
import requests, urllib
from extract_walmart_data import WalmartScraper

class WalmartShelfScraper(WalmartScraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = 'Expected URL format is http(s)://www.walmart.com/(tp|cp|browse)/*'

    BODY_COPY_XPATH = '//div[@class="ExpandableHtmlText-markup"]'
    URL_FORMAT_REGEX = r'^https?://www\.walmart\.com/(tp|cp|browse)/.*$'

    def __init__(self, **kwargs):
        WalmartScraper.__init__(self, **kwargs)

        self.product_data = None

    def check_url_format(self):
        if re.match(self.URL_FORMAT_REGEX, self.product_page_url):

            # transform /tp/ urls into search queries
            if re.match('https?://www\.walmart\.com/tp/', self.product_page_url):
                query = re.match('https?://www\.walmart\.com/tp/(.*)', self.product_page_url).group(1)
                query = re.sub('-', ' ', query)
                self.product_page_url = 'https://www.walmart.com/search/?query=' + urllib.quote(query)

            return True

        return False

    def not_a_product(self):
        self._get_product_data()
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _get_product_data(self):
        self.product_data = json.loads(re.search('window.__WML_REDUX_INITIAL_STATE__ = ({.*?});', self.page_raw_text).group(1))

    def _image_urls(self):
        items = self._get_items()
        return map(lambda i: i['imageUrl'].split('?')[0], items)

    def _image_count(self):
        images = self._image_urls()
        return len(images) if images else 0

    def _results_per_page(self):
        return len(self._get_items())

    def _get_items(self):
        items = []

        if self.product_data.get('preso'):
            items = self.product_data['preso']['items']

        if not items and self.product_data.get('ads'):
            items = self.product_data['ads']['result']['adModules'][0]['products']

        if not items:
            for item in self.product_data['presoData']['modules']['center']:
                items += item.get('data', [])

        return items

    def _get_prices(self, s):
        items = self._get_items()

        if self.product_data.get('preso'):
            return map(lambda p: p['primaryOffer'].get('offerPrice') or p['primaryOffer'][s], items)

        elif self.product_data.get('ads'):
            return map(lambda p: p['price'].get('currentPrice') or p['price'][s], items)

    def _lowest_item_price(self):
        prices = self._get_prices('minPrice')
        if prices:
            return min(prices)

    def _highest_item_price(self):
        prices = self._get_prices('maxPrice')
        if prices:
            return max(prices)

    def _body_copy(self):
        body_copy = ''

        for elem in self.tree_html.xpath(self.BODY_COPY_XPATH)[0]:
            body_copy += html.tostring(elem)

        if body_copy:
            return body_copy

    def _body_copy_links(self):
        if not self._body_copy():
            return None

        links = self.tree_html.xpath(self.BODY_COPY_XPATH + '//a/@href')

        return_links = {'self_links' : {'count': 0},
                        'broken_links' : {'links' : {}, 'count' : 0}}

        for link in links:
            if link == self.product_page_url:
                return_links['self_links']['count'] += 1

            else:
                status_code = requests.head(link).status_code

                if not status_code == 200:
                    return_links['broken_links']['links'][link] = status_code
                    return_links['broken_links']['count'] += 1

        return return_links

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        data = self.product_data['presoData']['modules']['top'][0]['data']
        return map(lambda d: d['name'], data)

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE

        # CONTAINER : PRODUCT_INFO

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count" : _image_count,\
        "image_urls" : _image_urls, \
        "results_per_page" : _results_per_page, \
        "lowest_item_price" : _lowest_item_price, \
        "highest_item_price" : _highest_item_price, \
        "body_copy" : _body_copy, \
        "body_copy_links" : _body_copy_links, \

        # CONTAINER : REVIEWS

        # CONTAINER : SELLERS

        # CONTAINER : CLASSIFICATION
        "categories": _categories, \
        }

    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = { \
    }
