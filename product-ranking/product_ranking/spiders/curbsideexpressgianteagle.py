# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import traceback
import json

from scrapy import Request

from product_ranking.items import (SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults


class CurbsideExpressGiantEagleProductsSpider(BaseProductsSpider):
    name = 'curbsideexpressgianteagle_products'
    allowed_domains = ["curbsideexpress.gianteagle.com"]

    PRODUCT_API_URL = "https://curbsideexpress.gianteagle.com/api/product/v7/product/store/{store}/sku/{sku}"
    PRODUCT_URL = 'https://curbsideexpress.gianteagle.com/store/{store}#/product/sku/{sku}'
    HEADERS = {
        'Accept': 'application/vnd.mywebgrocer.product+json',
        'Authorization': ''
    }
    START_URL = 'https://curbsideexpress.gianteagle.com/'
    STORE_JSON = 'https://curbsideexpress.gianteagle.com/api/stores/v7/chains/9F96429/stores' \
                 '?skip=0' \
                 '&coordinates={location}' \
                 '&radius=30' \
                 '&unitOfMeasure=mi&take=999'
    SELECT_STORE_URL = 'https://curbsideexpress.gianteagle.com/store/{store}'
    SEARCH_URL = 'https://curbsideexpress.gianteagle.com/store/{store}/#/search/{search_term}'
    SEARCH_API_URL = 'https://curbsideexpress.gianteagle.com/api/product/v7/products/store/{store}/search' \
                 '?skip={current_nums}' \
                 '&take=20' \
                 '&userId={user_id}' \
                 '&q={search_term}'

    def __init__(self, *args, **kwargs):
        self.store = kwargs.get('store', 'C9CC1102')
        url_formatter = FormatterWithDefaults(store=self.store)
        super(CurbsideExpressGiantEagleProductsSpider, self).__init__(url_formatter=url_formatter, *args, **kwargs)

    def start_requests(self):
        for request in super(CurbsideExpressGiantEagleProductsSpider, self).start_requests():
            if not self.product_url:
                request = request.replace(callback=self._parse_search)
            yield request

    def _parse_single_product(self, response):
        url = response.request.url
        if 'Error.html' in response.url:
            return Request(
                url=url,
                meta=response.meta
            )
        sku = url.split('/')[-1]
        token = self.get_token(response)
        store = re.search(r'store\/(.*?)#?(?:\/|\?)', url)

        if token and store:
            url = self.PRODUCT_API_URL.format(store=store.group(1), sku=sku)
            headers = self.get_headers(token)
            headers['Accept'] = 'application/vnd.mywebgrocer.product+json'
            return Request(
                url,
                callback=self.parse_product,
                headers=self.get_headers(token),
                meta=response.meta
            )
        return response.meta.get('product')

    def _parse_search(self, response):
        token = self.get_token(response)
        user_id = re.findall(r'"UserId":"(.*?)"', response.body)
        if user_id and token:
            user_id = user_id[0]
            url = self.SEARCH_API_URL.format(
                store=self.store,
                current_nums=0,
                user_id=user_id,
                search_term=response.meta.get('search_term')
            )
            headers = self.get_headers(token)
            headers['Accept'] = 'application/vnd.mywebgrocer.grocery-list+json'
            return Request(
                url,
                headers=headers,
                meta=response.meta
            )

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        try:
            product_json = json.loads(response.body)
        except:
            self.log('Error when parsing product json: {}'.format(traceback.format_exc()))
            cond_set_value(product, 'not_found', True)
            return product

        # Parse title
        title = self._parse_title(product_json)
        cond_set_value(product, 'title', title)

        # Parse brand
        brand = self._parse_brand(product_json)
        cond_set_value(product, 'brand', brand)

        # Parse sku
        sku = self._parse_sku(product_json)
        cond_set_value(product, 'sku', sku)

        # Parse image url
        image_url = self._parse_image_url(product_json)
        cond_set_value(product, 'image_url', image_url)

        # Parse price
        price = self._parse_price(product_json)
        cond_set_value(product, 'price', price)

        # Parse was_now
        was_now = self._parse_was_now(product_json)
        cond_set_value(product, 'was_now', was_now)

        # Parse price_per_volume
        price_per_volume = self._parse_price_per_volume(product_json)
        cond_set_value(product, 'price_per_volume', price_per_volume)

        # Parse volume_measure
        volume_measure = self._parse_volume_measure(product_json)
        cond_set_value(product, 'volume_measure', volume_measure)

        # Parse description
        description = self._parse_description(product_json)
        cond_set_value(product, 'description', description)

        # Parse reseller_id
        reseller_id = re.findall(r'store\/(.*?)\/sku', response.url)
        if reseller_id:
            cond_set_value(product, 'reseller_id', reseller_id[0])

        # Parse no_longer_available
        no_longer_available = self._parse_no_longer_available(product_json)
        cond_set_value(product, 'no_longer_available', no_longer_available)

        # Parse is_out_of_stock
        is_out_of_stock = self._parse_is_out_of_stock(product_json)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        cond_set_value(product, 'store', self.store)

        return product

    def _parse_title(self, product_json):
        brand = self._parse_brand(product_json)
        return brand + ' ' + product_json.get('Name') if brand and product_json.get('Name') else None

    @staticmethod
    def _parse_brand(product_json):
        return product_json.get('Brand')

    @staticmethod
    def _parse_sku(product_json):
        return product_json.get('Sku')

    @staticmethod
    def _get_current_price(product_json):
        price_data = product_json.get('CurrentPrice') or ''
        price = re.findall(r'(\d+[.]*\d*)', price_data)
        if price and len(price) == 2 and 'for' in price_data:
            price = float(price[1]) / float(price[0])
        elif price:
            price = float(price[0])
        else:
            price = None
        return price

    @staticmethod
    def _get_old_price(product_json):
        old_price = re.findall(r'(\d+[.]*\d*)', product_json.get('RegularPrice') or '')
        return old_price[0] if old_price else None

    def _parse_was_now(self, product_json):
        now = self._get_current_price(product_json)
        was = self._get_old_price(product_json)
        return '{}, {}'.format(now, was) if was and now else None

    @staticmethod
    def _parse_price_per_volume(product_json):
        price_per_volume = product_json.get('CurrentUnitPrice')
        return price_per_volume.split('/')[0] if price_per_volume else None

    @staticmethod
    def _parse_volume_measure(product_json):
        volume_measure = product_json.get('CurrentUnitPrice')
        return volume_measure.split('/')[1] if volume_measure and '/' in volume_measure else None

    def _parse_price(self, product_json):
        price = self._get_current_price(product_json)
        return Price(price=price, priceCurrency='USD') if price else None

    @staticmethod
    def _parse_image_url(product_json):
        image_urls = product_json.get('ImageLinks', [])
        for image_url in image_urls:
            if image_url.get('Rel') == 'large':
                return image_url.get('Uri')

    @staticmethod
    def _parse_description(product_json):
        desc = product_json.get('Description')
        return '<div>' + desc + '</div>' if desc else None

    @staticmethod
    def _parse_no_longer_available(product_json):
        no_longer_available = not product_json.get('IsAvailable', False)
        return no_longer_available

    @staticmethod
    def _parse_is_out_of_stock(product_json):
        is_out_of_stock = not product_json.get('InStock', False)
        return is_out_of_stock

    @staticmethod
    def get_token(response):
        token = re.findall(r'"Token":"(.*?)"', response.body)
        return token[0] if token else None
    
    def get_headers(self, token):
        headers = self.HEADERS
        headers['Authorization'] = token
        return headers

    def _get_products(self, response):
        for request in super(CurbsideExpressGiantEagleProductsSpider, self)._get_products(response):
            request = request.replace(dont_filter=True)
            if 'search?skip' not in request.url:
                request = request.replace(callback=self._parse_single_product)
            yield request

    def _scrape_total_matches(self, response):
        try:
            contents = json.loads(response.body)
            self.total_matches = int(contents.get('ItemCount', 0))
            return self.total_matches
        except:
            self.log('Error Parsing Products Json for Search Term: {}'.format(traceback.format_exc()))

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        try:
            contents = json.loads(response.body)
            items = contents.get('Items', [])
        except:
            items = []
            self.log('Error Parsing Products Json for Search Term Json: {}'.format(traceback.format_exc()))

        for item in items:
            res_item = SiteProductItem()
            link = self.PRODUCT_URL.format(store=self.store, sku=item.get('Sku'))
            yield link, res_item

    def _scrape_next_results_page_link(self, response):
        try:
            contents = json.loads(response.body)
            page_links = contents.get('PageLinks', [])
            for link in page_links:
                if link.get('Rel') == 'next':
                    # return link.get('Uri')
                    return Request(
                        link.get('Uri'),
                        meta=response.meta,
                        headers=response.request.headers
                    )
        except:
            self.log('Error Parsing Products Json for Search Term Json: {}'.format(traceback.format_exc()))