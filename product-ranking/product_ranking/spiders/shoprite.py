"""This is a base shoprite scraper module"""
# -*- coding: utf-8 -*-
import re
import json
import time
import urllib
import traceback
from scrapy.log import INFO
from scrapy import Request
from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX


class ShopriteProductsSpider(BaseProductsSpider):
    """This is a base shoprite.com class"""
    name = "shoprite_products"
    allowed_domains = ["shoprite.com"]

    PRODUCT_URL = "https://shop.shoprite.com/api/product/v7/chains/FBFB139/stores/{store}/skus/{sku}"

    SCREEN_URL = "https://shop.shoprite.com/store/{store}/browser/screen?width=1920&height=1080"

    SEARCH_URL = "https://shop.shoprite.com/store/{store}#/search/{search_term}" \
                 "/1?queries=sort=Relevance"

    PRODUCTS_URL = "https://shop.shoprite.com/api/product/v7/products/store/{store}" \
                   "/search?sort=MyPastPurchases&skip={skip}&take=20&userId={user_id}&q={search_term}&sponsored=0"

    STOREMAP_URL = "http://plan.shoprite.com/Stores/Get?PostalCode={zip_code}&Radius=20&Units=Miles&StoreType=Cir&" \
                   "StoresPageSize=undefined&IsShortList=undefined&_={timestamp}"

    TOKEN_URL = "https://shop.shoprite.com/store/{store}#/"

    def __init__(self, *args, **kwargs):
        """Initiate input variables and etc."""
        super(ShopriteProductsSpider, self).__init__(*args, **kwargs)
        self.store = kwargs.pop('store', None)
        self.zip_code = kwargs.pop('zip_code', None)
        if not (self.store or self.zip_code):
            self.store = '0624283'
            if self.product_url:
                store = re.search('store/(.*?)#', self.product_url)
                if store:
                    self.store = store.group(1).strip()

    def start_requests(self):
        if self.zip_code and not self.store:
            yield Request(
                self.STOREMAP_URL.format(zip_code=self.zip_code, timestamp=format(time.time() * 1000, ".0f")),
                callback=self._get_codemap)
            return
        yield Request(self.TOKEN_URL.format(store=self.store), callback=self._parse_helper)

    def _get_codemap(self, response):
        zips = response.xpath('//input[@value="Store"]/@data-clientanalyticslabel').extract()
        if zips:
            self.store = zips[0]
            return self.start_requests()
        else:
            self.log("There are no stores for given zip code, quitting...")

    def _parse_helper(self, response):
        meta = response.meta
        meta['configuration'] = self._parse_info(
            response) if not meta.get('configuration') else meta.get('configuration')
        meta['token'] = self._parse_token(
            meta.get('configuration')) if not meta.get('token') else meta.get('token')
        meta['user_id'] = self._parse_user_id(
            meta.get('configuration')) if not meta.get('user_id') else meta.get('user_id')

        self.zip_code = self._parse_zipcode(meta.get('configuration'))

        headers = {}
        headers['Authorization'] = meta.get('token')
        headers['Referer'] = response.url
        headers['Accept'] = 'application/vnd.mywebgrocer.wakefern-product+json'
        for search_term in self.searchterms:
            headers['Accept'] = 'application/vnd.mywebgrocer.wakefern-product-list+json'
            response.meta.update({'search_term': search_term, 'remaining': self.quantity})
            yield Request(self.PRODUCTS_URL.format(user_id=meta.get('user_id'),
                                                   store=self.store,
                                                   search_term=search_term,
                                                   skip=response.meta.get('skip', 0)),
                          headers=headers,
                          meta=response.meta)
        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            prod['reseller_id'] = self._parse_sku_url(self.product_url)
            self.store = self._parse_store(self.product_url)
            yield Request(self.PRODUCT_URL.format(store=self.store, sku=prod['reseller_id']),
                          self._parse_single_product,
                          meta={'product': prod},
                          headers=headers)

        if self.products_url:
            urls = self.products_url.split('||||')
            for url in urls:
                prod = SiteProductItem()
                prod['url'] = url
                prod['search_term'] = ''
                prod['reseller_id'] = self._parse_sku_url(url)
                yield Request(self.PRODUCT_URL.format(store=self.store, sku=prod['reseller_id']),
                              self._parse_single_product,
                              meta={'product': prod})

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body)
            return data.get('TotalQuantity')
        except:
            self.log("Found no total matches {}".format(traceback.format_exc()))
            return 0

    def _scrape_product_links(self, response):
        try:
            products = json.loads(response.body).get('Products')
            for product_info in products:
                yield None, self.parse_product(response, product_info)
        except:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        try:
            info = json.loads(response.body)
            page = info.get('PageLinks')[-1]
            skip = info.get('Skip') + 20
            if page.get('Rel') == 'next':
                response.meta['skip'] = skip
                return Request(self.PRODUCTS_URL.format(user_id=response.meta['user_id'],
                                                        store=self.store,
                                                        search_term=response.meta['search_term'],
                                                        skip=response.meta.get('skip', 0)),
                               headers={
                                   'Accept': 'application/vnd.mywebgrocer.wakefern-product-list+json',
                                   'Authorization': response.meta.get('token')
                               },
                               meta=response.meta)
        except:
            self.log("Error while parsing json data".format(traceback.format_exc()))

    @staticmethod
    def _parse_title(product_info):
        title = product_info.get('Brand') + " " + product_info.get('Name')
        return title

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
    def _parse_category(product_info):
        return product_info.get('Category')

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
        return configuration.get('CurrentUser', {}).get('UserId')

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
        return 'https://shop.shoprite.com' \
               '/store/{store}#/product/sku/{sku}'.format(store=store, sku=sku)

    @staticmethod
    def _parse_unit_price(product_info):
        unit_price = product_info.get('CurrentUnitPrice')
        return unit_price

    @staticmethod
    def _parse_price_per_volume(unit_price):
        price_per_volume = None
        if unit_price:
            price_per_volume = re.findall(FLOATING_POINT_RGEX, unit_price)
        return price_per_volume[0] if price_per_volume else None

    @staticmethod
    def _parse_volume_measure(unit_price):
        volume_measure = None
        if unit_price:
            volume_measure = unit_price.split('/')[-1]
        return volume_measure if volume_measure else None

    @staticmethod
    def _parse_zipcode(configuration):
        return configuration.get('StoreAddress', {}).get('Zip')

    def _parse_single_product(self, response):
        """Same to parse_product."""
        return self.parse_product(response)

    def parse_product(self, response, product_info=None):
        """Handles parsing of a product page."""
        product = response.meta['product'] if response.meta.get('product') else SiteProductItem()
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

        # Parse price
        price = self._parse_price(product_info)
        cond_set_value(product, 'price', price)

        # Parse img_url
        image_url = self._parse_image_url(product_info)
        cond_set_value(product, 'image_url', image_url)

        unit_price = self._parse_unit_price(product_info)

        # Parse price_per_volume
        price_per_volume = self._parse_price_per_volume(unit_price)
        cond_set_value(product, 'price_per_volume', price_per_volume)

        # Parse volume_measure
        volume_measure = self._parse_volume_measure(unit_price)
        cond_set_value(product, 'volume_measure', volume_measure)

        cond_set_value(product, 'store', self.store)

        cond_set_value(product, 'zip_code', self.zip_code)

        # Parse url
        if not product.get('url'):
            url = self._parse_url(self.store, sku)
            cond_set_value(product, 'url', url)

        return product
