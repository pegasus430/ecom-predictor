# -*- coding: utf-8 -*-
"""This is a base harristeeter scraper module"""
import json
import re
import urllib
import traceback

from scrapy import Request
from scrapy.conf import settings

from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import (FLOATING_POINT_RGEX, BaseProductsSpider,
                                     cond_set_value)


class HarristeeterProductsSpider(BaseProductsSpider):
    """This is a base harristeeter.com class"""
    name = "harristeeter_products"
    allowed_domains = ["harristeeter.com"]

    PRODUCT_URL = "https://shop.harristeeter.com/api/product/v5/product/store/{store}/sku/{sku}"
    SCREEN_URL = "https://shop.harristeeter.com/store/{store}/browser/screen?width=1920&height=1080"
    SEARCH_URL = "https://shop.harristeeter.com/store/{store}#/search/{search_term}" \
                 "/1?queries=sort=Relevance"
    PRODUCTS_URL = "https://shop.harristeeter.com/api/product/v5/products/store/{store}" \
                   "/search?sort=Relevance&skip={skip}&take=20&userId={user_id}&q={search_term}"
    handle_httpstatus_list = [404]

    def __init__(self, store='10C9127028', *args, **kwargs):
        """Initiate input variables and etc."""
        super(HarristeeterProductsSpider, self).__init__(*args, **kwargs)
        self.store = kwargs.get('store', store)
        settings.overrides['USE_PROXIES'] = True
        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        RETRY_HTTP_CODES = settings.get('RETRY_HTTP_CODES', [])
        if 404 in RETRY_HTTP_CODES:
            RETRY_HTTP_CODES.remove(404)

    def start_requests(self):
        """Generate Requests from the SEARCH_URL and the search terms."""
        for search_term in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    store=self.store,
                    search_term=urllib.quote_plus(search_term.encode('utf-8')),
                ),
                meta={'search_term': search_term, 'remaining': self.quantity},
                callback=self._parse_helper
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod})

        if self.products_url:
            urls = self.products_url.split('||||')
            for url in urls:
                prod = SiteProductItem()
                prod['url'] = url
                prod['search_term'] = ''
                yield Request(url,
                              self._parse_single_product,
                              meta={'product': prod})

    def _parse_helper(self, response):
        meta = response.meta
        meta['configuration'] = self._parse_info(
            response) if not meta.get('configuration') else meta.get('configuration')
        meta['token'] = self._parse_token(
            meta.get('configuration')) if not meta.get('token') else meta.get('token')
        meta['user_id'] = self._parse_user_id(
            meta.get('configuration')) if not meta.get('user_id') else meta.get('user_id')
        headers = {}
        headers['Authorization'] = meta.get('token')
        headers['Referer'] = response.url
        headers['Accept'] = 'application/vnd.mywebgrocer.grocery-list+json'
        return Request(self.PRODUCTS_URL.format(user_id=meta.get('user_id'),
                                                store=self.store,
                                                search_term=response.meta.get('search_term'),
                                                skip=response.meta.get('skip', 0)),
                       headers=headers,
                       meta=meta)

    @staticmethod
    def _scrape_total_matches(response):
        return json.loads(response.body).get('TotalQuantity')

    def _scrape_product_links(self, response):
        products = json.loads(response.body).get('Items')
        for product_info in products:
            yield None, self.parse_product(response, product_info)

    def _scrape_next_results_page_link(self, response):
        try:
            info = json.loads(response.body)
            page = info.get('PageLinks')[-1]
            skip = info.get('Skip') + 20
            if page.get('Rel') == 'next':
                response.meta['skip'] = skip
                return self._parse_helper(response)
        except:
            self.log("Found no product {}".format(traceback.format_exc()))
            return None

    @staticmethod
    def _scrape_results_per_page(response):
        pass

    @staticmethod
    def _parse_title(product_info):
        return product_info.get('Name')

    @staticmethod
    def _parse_price(product_info):
        currency = 'USD'
        price_raw = product_info.get('CurrentPrice', '')
        price = FLOATING_POINT_RGEX.findall(price_raw)
        if not price or 'for' in price_raw:
            price_raw = product_info.get('RegularPrice', '')
            price = FLOATING_POINT_RGEX.findall(price_raw)
        price = float(price[0]) if price else 0.0
        return Price(price=price, priceCurrency=currency)

    @staticmethod
    def _parse_description(product_info):
        return product_info.get('Description')

    @staticmethod
    def _parse_image_url(product_info):
        try:
            image_url = product_info.get('ImageLinks')[1].get('Uri')
        except IndexError:
            image_url = None
        return image_url

    @staticmethod
    def _parse_categories(response):
        pass

    @staticmethod
    def _parse_category(product_info):
        return product_info.get('Category')

    @staticmethod
    def _parse_categories_full_info(categories_names, categories_links):
        pass

    @staticmethod
    def _parse_categories_links(response):
        pass

    @staticmethod
    def _parse_brand(product_info):
        return product_info.get('Brand')

    @staticmethod
    def _parse_store(url):
        store = re.findall(r'\/store\/([\d\w]+)\?*.*?\#', url)
        return store[0] if store else None

    @staticmethod
    def _parse_sku_url(url):
        sku = re.findall(r'\#\/product\/sku\/(\d+)', url)
        return sku[0] if sku else None

    @staticmethod
    def _parse_info(response):
        info = response.xpath(
            '//script[contains(text(), "var configuration =")]/text()'
        ).re(r'var configuration = (\{.+?\});')
        return json.loads(info[0]) if info else {}

    @staticmethod
    def _parse_token(configuration):
        return configuration.get('Token')

    @staticmethod
    def _parse_user_id(configuration):
        return configuration.get('CurrentUser').get('UserId')

    @staticmethod
    def _parse_entry_url(configuration):
        return configuration.get('EntryUrl')

    @staticmethod
    def _parse_sku(product_info):
        return product_info.get('Sku')

    @staticmethod
    def _parse_is_out_of_stock(product_info):
        return not product_info.get('InStock')

    @staticmethod
    def _parse_no_longer_available(product_info):
        return not product_info.get('IsAvailable')

    @staticmethod
    def _parse_url(store, sku):
        return 'https://shop.harristeeter.com' \
               '/store/{store}#/product/sku/{sku}'.format(store=store, sku=sku)

    def _parse_single_product(self, response):
        """Same to parse_product."""
        url = response.meta.get('product').get('url')
        store = self._parse_store(url)
        sku = self._parse_sku_url(url)
        configuration = self._parse_info(response)
        token = self._parse_token(configuration)
        headers = {}
        headers['Authorization'] = token
        headers['Referer'] = response.url
        headers['Accept'] = 'application/vnd.mywebgrocer.shop-entry+json'
        return Request(self.PRODUCT_URL.format(store=store, sku=sku),
                       headers=headers,
                       callback=self.parse_product,
                       meta=response.meta)

    def _parse_shelf_path(self):
        return None

    def _parse_shelf_name(self):
        return None

    def parse_product(self, response, product_info=None):
        """Handles parsing of a product page."""
        product = response.meta.get('product', SiteProductItem())
        if response.status == 404:
            product['not_found'] = True
            return product
        else:
            product['not_found'] = False

        # Set locale
        product['locale'] = 'en_US'

        # Parse json
        if product_info:
            product_info = product_info
        else:
            product_info = json.loads(response.body)

        # Parse title
        title = self._parse_title(product_info)
        cond_set_value(product, 'title', title)

        # Parse brand
        brand = self._parse_brand(product_info)
        cond_set_value(product, 'brand', brand)

        # Parse categroy
        category = self._parse_category(product_info)
        cond_set_value(product, 'category', category)

        # Parse sku
        sku = self._parse_sku(product_info)
        cond_set_value(product, 'sku', sku)

        # Parse reseller_id
        cond_set_value(product, 'reseller_id', sku)

        # Parse description
        description = self._parse_description(product_info)
        cond_set_value(product, 'description', description)

        # Parse is_out_of_stock
        is_out_of_stock = self._parse_is_out_of_stock(product_info)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse no_longer_available
        no_longer_available = self._parse_no_longer_available(product_info)
        cond_set_value(product, 'no_longer_available', no_longer_available)

        # Parse shelf_path
        shelf_path = self._parse_shelf_path()
        cond_set_value(product, 'shelf_path', shelf_path)

        # Parse shelf_name
        shelf_name = self._parse_shelf_name()
        cond_set_value(product, 'shelf_name', shelf_name)

        # Parse price
        price = self._parse_price(product_info)
        cond_set_value(product, 'price', price)

        # Parse img_url
        image_url = self._parse_image_url(product_info)
        cond_set_value(product, 'image_url', image_url)

        # Parse url
        if not product.get('url'):
            url = self._parse_url(self.store, sku)
            cond_set_value(product, 'url', url)

        return product
