# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals
import json
import re

from product_ranking.items import SiteProductItem, RelatedProduct, Price
from product_ranking.spiders import BaseProductsSpider
from product_ranking.spiders import cond_set, cond_set_value

from scrapy.log import DEBUG
import urllib
from scrapy.http import Request


class JumboMobileProductsSpider(BaseProductsSpider):
    name = 'jumbo_mobile_products'
    allowed_domains = ["jumbo.com"]
    SEARCH_URL = "https://mobileapi.jumbo.com/v2/products?count=10&offset={offset}&q={search_term}"
    PRODUCT_URL = "https://mobileapi.jumbo.com/api/products/{product_id}"

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        try:
            response = json.loads(response.body)
        except:
            self.log("Failed to load json from response.", DEBUG)
            return product

        message = response.get('message', [])
        if 'Not Found' in message:
            return product

        try:
            response = response.get('product')
            response = response.get('data')
        except:
            self.log("Failed to load product.", DEBUG)
            return product

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        # Parse out of stock
        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse reseller id
        _reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', _reseller_id)

        # Parse upc
        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc)

        # Parse categories
        category = self._parse_category(response)
        cond_set_value(product, 'categories', category)
        #
        cond_set_value(product, 'category', category) if category else None

        # Parse variants
        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)
        return product

    @staticmethod
    def _parse_reseller_id(response):
        _id = response.get('id')
        return _id

    @staticmethod
    def _parse_brand(response):
        try:
            web_address = response.get('brandInfo', {}).get('webAddress')
            brand = web_address.replace('www.', '').split('.')[0]
            return brand
        except:
            return None

    @staticmethod
    def _parse_title(response):
        title = response.get('title')
        return title

    @staticmethod
    def _parse_out_of_stock(response):
        is_out_of_stock = response.get('available')
        return not (is_out_of_stock)

    @staticmethod
    def _parse_price(response):
        label = response.get('promotion', {}).get('label')

        try:
            price = float(response.get('prices').get('price').get('amount'))
            price = price / 100
        except:
            price = 0

        if label:
            if 'gratis' in label:
                price = round(price / 2, 2)
            elif 'korting' in label:
                pattern = r'(\d*)'
                bonus = re.findall(pattern, label)
                if bonus:
                    bonus = bonus[0]
                    try:
                        bonus = float(bonus) / 100
                    except:
                        bonus = 0
                    price = round((1 - bonus) * price, 2)
            elif 'voor' in label:
                pattern = r'[\d\,]+'
                try:
                    amount = re.findall(pattern, label)[0]
                    bonus = re.findall(pattern, label)[1]
                    bonus = bonus.replace(',', '.')
                    price = round(float(bonus) / float(amount), 2)
                except:
                    pass
        return Price(priceCurrency="EUR", price=price)

    @staticmethod
    def _parse_description(response):
        return response.get('detailsText')

    @staticmethod
    def _parse_image_url(response):
        image_url = response.get('imageInfo')
        if image_url:
            image_url = image_url.get('primaryView')
            if image_url:
                image_url = image_url[0]
                image_url = image_url.get('url')
        return image_url

    @staticmethod
    def _parse_upc(response):
        return None

    @staticmethod
    def _parse_category(response):
        return response.get('topLevelCategory')

    @staticmethod
    def _parse_variants(response):
        return None

    def _scrape_total_matches(self, response):
        try:
            response = json.loads(response.body)
        except:
            return 0
        return response.get('products', {}).get('total')

    def _scrape_product_links(self, response):
        try:
            search_results = json.loads(response.body)
            search_results = search_results.get('products', {})
        except:
            search_results = {}
            self.log("No links found.", DEBUG)

        search_results = search_results.get('data')
        if search_results:
            for product in search_results:
                product_id = product.get('id')

                prod = SiteProductItem()

                yield Request(self.url_formatter.format(
                    self.PRODUCT_URL,
                    product_id=product_id.encode('utf-8')),
                    callback=self._parse_single_product,
                    meta={'product': prod}), prod

    def _scrape_next_results_page_link(self, response):
        search_term = response.request.meta
        search_term = search_term.get('search_term')

        total_matches = self._scrape_total_matches(response)
        url = response.url

        offset_pattern = r'(?<=offset\=)(\d*?)(?=&)'
        offset = re.findall(offset_pattern, url)
        if offset:
            try:
                offset = offset[0]
                offset = int(offset)
            except:
                self.log("Failed to get offset.", DEBUG)
                return None

            if offset <= total_matches:
                offset += 10
                offset = str(offset)
                next_page = self.url_formatter.format(self.SEARCH_URL, offset=offset, search_term=search_term)

                return next_page

    def start_requests(self):

        if self.searchterms:
            for st in self.searchterms:
                yield Request(
                    self.url_formatter.format(
                        self.SEARCH_URL,
                        search_term=urllib.quote_plus(st.encode('utf-8')),
                        offset=0,
                    ),
                    meta={
                        'search_term': st,
                        'remaining': self.quantity
                    },
                )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''

            yield Request(self.get_single_product_url(self.product_url),
                          self._parse_single_product,
                          meta={'product': prod})

        if self.products_url:
            urls = self.products_url.split('||||')

            for url in urls:
                prod = SiteProductItem()
                prod['url'] = url
                prod['search_term'] = ''

                yield Request(self.get_single_product_url(url),
                              self._parse_single_product,
                              meta={'product': prod})

    def get_single_product_url(self, url):
        """Cuts product id from given url and merge it to mobileapi address"""
        pattern = r'(?<=\/)\w*(?=\/\Z|\Z)'
        product_id = re.findall(pattern, url)
        product_id = product_id[0] if product_id else '0'

        url = self.url_formatter.format(
            self.PRODUCT_URL,
            product_id=product_id.encode('utf-8'))
        return url
