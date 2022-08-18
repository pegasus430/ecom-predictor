from __future__ import absolute_import, division, unicode_literals

import base64
import json
import re
import traceback
import urllib

from urlparse import urljoin
from scrapy import Request
from scrapy.conf import settings
from scrapy.log import WARNING
from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider, FormatterWithDefaults,
                                     cond_set, cond_set_value)
from product_ranking.validation import BaseValidator
from product_ranking.validators.boxed_validator import BoxedValidatorSettings

class BoxedProductsSpider(BaseValidator, BaseProductsSpider):
    name = "boxed_products"
    allowed_domains = ["www.boxed.com"]
    handle_httpstatus_list = [404, 500]
    payload = 'searchPayload'

    SEARCH_URL = 'https://www.boxed.com/products/search/{search_term}/?sort={search_sort}'
    SEARCH_SORT = {
        'default': '',
        'newest': '-addDate',
        'price': 'price',
        'sale': '-onSale'
    }

    settings = BoxedValidatorSettings

    def __init__(self, search_sort='default', *args, **kwargs):
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.CustomClientContextFactory'

        super(BoxedProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                search_sort=self.SEARCH_SORT[search_sort],
            ),
            *args,
            **kwargs)
        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                          "Chrome/61.0.3163.100 Safari/537.36"

    def start_requests(self):
        if not self.searchterms:
            for request in super(BoxedProductsSpider, self).start_requests():
                request = request.replace(dont_filter=True)
                yield request

        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8').replace(' ', '-')),
                ),
                meta={'search_term': st, 'remaining': self.quantity},
                headers=self._get_api_headers()
            )

    def _get_api_headers(self):
        return {
            'api-json': 'true',
            'Host': self.allowed_domains[0],
        }

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        if response.status == 404:
            product['not_found'] = True
            return product

        product_data = self._extract_product_data(response)

        if product_data:
            main_product_variant = self._parse_main_product_variant(product_data)
        else:
            return product

        if not main_product_variant:
            return

        title = self._parse_title(main_product_variant)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(main_product_variant)
        cond_set_value(product, 'brand', brand)

        price = self._parse_price(main_product_variant)
        cond_set_value(product, 'price', price)

        price_original = self._parse_price_original(main_product_variant)
        cond_set_value(product, 'price_original', price_original)

        upc = self._parse_upc(main_product_variant)
        cond_set_value(product, 'upc', upc)

        is_out_of_stock = self._parse_is_out_of_stock(main_product_variant)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        sku = self._parse_sku(main_product_variant)
        cond_set_value(product, 'sku', sku)

        reseller_id = self._parse_reseller_id(main_product_variant)
        cond_set_value(product, 'reseller_id', reseller_id)

        image_url = self._parse_image_url(main_product_variant)
        cond_set_value(product, 'image_url', image_url)

        categories = self._parse_categories(response)
        if categories:
            cond_set_value(product, 'categories', categories)
            cond_set_value(product, 'category', categories[-1])
            cond_set_value(product, 'department', categories[-1])

        model = self._parse_model(main_product_variant)
        cond_set_value(product, 'model', model)

        # TODO: add variants parsing
        if response.status in self.handle_httpstatus_list:
            cond_set_value(product, 'no_longer_available', True)

        return product

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body)

            return data['data'][self.payload]['productsTotalCount']
        except:
            return None

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body)
            products = data['data'][self.payload]['products']
        except:
            self.log("Error while parsing product links: {}".format(traceback.format_exc()))
            products = []

        for product in products:
            product_item = SiteProductItem()

            # items from search in stock always
            cond_set_value(product_item, 'is_out_of_stock', False)
            cond_set_value(product_item, 'no_longer_available', False)

            product_url = None

            if product.get('variant'):
                product_data = product.get('variant')

                if product_data.get('gid') and product_data.get('slug'):
                    product_url = '/product/{}/{}/'.format(product_data.get('gid'), product_data.get('slug'))
            elif product.get('product'):
                product_data = product.get('product')

                cond_set_value(product_item, 'title', product_data.get('name'))
                cond_set_value(product_item, 'brand', product_data.get('brand'))
                cond_set_value(product_item, 'sku', product_data.get('gid'))
                cond_set_value(product_item, 'reseller_id', product_data.get('gid'))

                cond_set_value(product_item, 'model', product_data.get('extendedName'))

                cond_set(product_item,
                         'image_url',
                         product_data.get('images'),
                         lambda x: 'http://{}'.format(x['originalBase']))

                variants = list()
                for i, variant_data in enumerate(product_data.get('variants')):
                    variant_data = variant_data.get('variant')
                    if variant_data:
                        variant = dict()

                        cond_set_value(variant, 'in_stock', True)
                        cond_set_value(variant, 'price', variant_data.get('price'))

                        if variant_data.get('gid') and variant_data.get('slug'):
                            cond_set_value(variant,
                                           'url',
                                           urljoin(response.url,
                                                   '/product/{}/{}/'.format(variant_data.get('gid'),
                                                                            variant_data.get('slug'))))

                        cond_set_value(variant, 'sku', variant_data.get('gid'))

                        if product.get('onSale'):
                            cond_set_value(variant, 'price_original', variant_data.get('standardPrice'))

                        if i == 0:
                            cond_set_value(variant, 'selected', True)
                        else:
                            cond_set_value(variant, 'selected', False)

                        cond_set(variant,
                                 'image_url',
                                 variant_data.get('images'), lambda x: 'http://{}'.format(x['originalBase']))

                        variants.append(variant)

                if variants:
                    cond_set_value(product_item, 'variants', variants)
            else:
                self.log('Unexpected data for product: {}'.format(json.dumps(product, indent=2)), WARNING)

            yield product_url, product_item

    def _scrape_next_results_page_link(self, response):
        try:
            data = json.loads(response.body)

            next_url = '/api{}'.format(data['data'][self.payload]['pagination']['paginationApiUrl'])

            return Request(urljoin(response.url, next_url),
                           headers=self._get_api_headers(),
                           meta=dict(response.meta),
                           priority=1)
        except:
            return None

    def _scrape_results_per_page(self, response):
        try:
            data = json.loads(response.body)

            return len(data['data'][self.payload]['products'])
        except:
            return None

    def _extract_product_data(self, response):
        base64_encoded_text_regexp = re.compile('var\s+BoxedAppState\s+=\s+\'(.+?)\';', re.DOTALL)
        base64_encoded_text = response.xpath(
            '//script[contains(., "BoxedAppState")]/text()'
        ).re(base64_encoded_text_regexp)

        try:
            return json.loads(base64.b64decode(base64_encoded_text[0]))
        except:
            self.log('Can not convert text to json: {}'.format(traceback.format_exc()))

    @staticmethod
    def _parse_main_product_variant(product_data):
        if product_data.get('productPayload'):
            return product_data.get('productPayload', {}).get('variant', {})

    @staticmethod
    def _parse_title(main_product_variant):
        return main_product_variant.get('nameText')

    @staticmethod
    def _parse_brand(main_product_variant):
        return main_product_variant.get('brandingText')

    @staticmethod
    def _parse_price(main_product_variant):
        price = main_product_variant.get('price')
        if price:
            return Price('USD', price)

    @staticmethod
    def _parse_price_original(main_product_variant):
        if main_product_variant.get('onSale'):
            return Price('USD', main_product_variant.get('standardPrice'))

    @staticmethod
    def _parse_is_out_of_stock(main_product_variant):
        return not main_product_variant.get('inStock')

    @staticmethod
    def _parse_upc(main_product_variant):
        return main_product_variant.get('upc')

    @staticmethod
    def _parse_sku(main_product_variant):
        return main_product_variant.get('sku')

    @staticmethod
    def _parse_reseller_id(main_product_variant):
        return main_product_variant.get('gid')

    @staticmethod
    def _parse_categories(response):
        return response.xpath(
            '//div[@id="page-content"]//div//section//div//span//a/text()'
        ).extract()

    @staticmethod
    def _parse_image_url(main_product_variant):
        images = main_product_variant.get('images')
        if images and 'originalBase' in images[0]:
            return 'http://{}'.format(images[0]['originalBase'])

    @staticmethod
    def _parse_model(main_product_variant):
        model = filter(
            None, [main_product_variant.get('extendedInfoText'), main_product_variant.get('extendedInfo2Text')]
        )
        if model:
            return ''.join(model)
