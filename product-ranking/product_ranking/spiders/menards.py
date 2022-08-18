# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals

import json
import re
import traceback
from collections import OrderedDict
from urlparse import urljoin

from scrapy import Request
from scrapy.conf import settings

from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider, FormatterWithDefaults,
                                     cond_set_value)


class MenardsProductsSpider(BaseProductsSpider):
    name = 'menards_products'
    allowed_domains = ["menards.com"]

    PRODUCT_API_URL = 'https://service.menards.com/ProductDetailsService/services/cxf/rest/v5/getInitialized' \
                      '/storeNumber/3598/machineType/external/sourceId/999/fulfillmentStoreNumber/3205?' \
                  'itemIds={product_id}'
    SEARCH_URL = 'https://www.menards.com/main/search.html?search={search_term}&page={page}&ipp=28'

    def __init__(self, *args, **kwargs):
        self.headers = OrderedDict(
            [('Host', ''),
             ('Accept-Encoding', 'gzip, deflate'),
             ('Accept-Language', 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4'),
             ('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36'),
             ('Accept','text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'),
             ('Connection', 'keep-alive')]
        )
        settings.overrides['USE_PROXIES'] = True
        settings.overrides['REFERER_ENABLED'] = False
        settings.overrides['COOKIES_ENABLED'] = False
        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.IncapsulaRequestMiddleware'] = 2

        url_formatter = FormatterWithDefaults(page=1)
        super(MenardsProductsSpider, self).__init__(url_formatter=url_formatter, *args, **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def start_requests(self):
        """Generate Requests from the SEARCH_URL and the search terms."""
        for request in super(MenardsProductsSpider, self).start_requests():
            if self.product_url:
                request = request.replace(
                    url=self.get_product_api_url(self._parse_product_id(self.product_url))
                )
            yield request

    def parse_product(self, response):
        product = response.meta['product']

        try:
            product_json = json.loads(response.body).get('itemMap').get(response.url.split('itemIds=')[-1])
        except:
            self.log('Cant not parse json: {}'.format(traceback.format_exc()))
            return None

        # Parse brand
        brand = product_json.get('brandName')
        cond_set_value(product, 'brand', brand)

        # Parse title
        title = product_json.get('title')
        cond_set_value(product, 'title', title)

        # Parse price
        price = self._parse_price(product_json)
        cond_set_value(product, 'price', price)

        # Parse UPC
        upc = product_json.get('properties').get('UPC')
        cond_set_value(product, 'upc', upc)

        # Parse sku
        sku = product_json.get('menardsSku')
        cond_set_value(product, 'sku', sku)

        # Parse model
        model = product_json.get('modelNumber')
        cond_set_value(product, 'model', model)

        # Parse image url
        image_url = self._parse_image_url(product_json)
        cond_set_value(product, 'image_url', image_url)

        # Parse product url
        product['url'] = self.construct_product_url(product_json)

        return product

    def _parse_price(self, product_json):
        price = product_json.get('priceAndStatusDTO', {}).get('rebatePriceDisplay')

        try:
            if not price:
                price = product_json.get('priceAndStatusDTO').get('priceDisplay')

            return Price(price=float(price[1:].replace(',', '')), priceCurrency='USD')
        except:
            self.log('Price extraction error {}'.format(traceback.format_exc()))

    @staticmethod
    def _parse_image_url(product_json):
        media_path = product_json.get('mediaPath')
        image = product_json.get('image')
        image_url = 'https://hw.menardc.com/main/' + media_path + '/ProductLarge/' + image if image else None
        return image_url

    def _scrape_product_links(self, response):
        product_links = response.xpath('//div[contains(@class, "ps-item")]'
                                       '//div[@class="ps-item-title"]'
                                       '/a/@href').extract()
        for link in product_links:
            link = self.get_product_api_url(self._parse_product_id(link))
            yield link, SiteProductItem()

    def _scrape_total_matches(self, response):
        total_matches = response.xpath('//span[@class="count"]/text()').re('(\d+) results found')
        if total_matches:
            return int(total_matches[0])

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page', 1)
        if current_page * 28 > self._scrape_total_matches(response):
            return None
        current_page += 1
        response.meta['current_page'] = current_page
        search_term = response.meta['search_term']
        url = self.SEARCH_URL.format(search_term=search_term, page=current_page)
        return Request(url=url, meta=response.meta)

    @staticmethod
    def _parse_product_id(url):
        product_id = re.search(r'p-(\d+)-c', url)
        if not product_id:
            product_id = re.search(r'p-(\d+)\.', url)
        if product_id:
            return product_id.group(1)

    def get_product_api_url(self, product_id):
        if product_id:
            return self.PRODUCT_API_URL.format(product_id=product_id)

    @staticmethod
    def construct_product_url(product_json):
        return urljoin(
            'https://www.menards.com/main/',
            '{}/p-{}-c-{}.htm'.format(
                product_json.get('seoURL'),
                product_json.get('itemId'),
                product_json.get('originalCategoryId'))
        )
