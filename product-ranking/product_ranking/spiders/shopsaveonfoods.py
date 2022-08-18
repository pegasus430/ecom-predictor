from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback

from scrapy.http import Request
from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value,\
    FormatterWithDefaults, FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator
from scrapy.log import WARNING


class ShopsaveonfoodsProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'shopsaveonfoods_products'
    allowed_domains = ["shop.saveonfoods.com"]

    START_URL = "https://shop.saveonfoods.com"

    PRODUCT_URL = "https://shop.saveonfoods.com/api/product/v7/product/store/{store}/sku/{sku}"

    SEARCH_URL = "https://shop.saveonfoods.com/api/product/v7/products/store/{store}/search" \
                 "?skip={offset}&take=20" \
                 "&userId={user_id}&q={search_term}"

    product_per_page = 20

    def __init__(self, *args, **kwargs):
        super(ShopsaveonfoodsProductsSpider, self).__init__(*args, **kwargs)
        self.store = kwargs.pop('store', None)

        if not self.store:
            self.store = 'D28B1082'
            if self.product_url:
                store = re.search('store/(.*?)\/#', self.product_url)
                if store:
                    self.store = store.group(1)

    def start_requests(self):
        yield Request(
            url=self.START_URL,
            callback=self.start_requests_with_csrf,
        )

    def start_requests_with_csrf(self, response):
        csrf = self.get_csrf(response)

        headers = {
            "Accept": "application/vnd.mywebgrocer.grocery-list+json",
            "Authorization": csrf,
            "X-Requested-With": "XMLHttpRequest",
        }

        if not self.product_url:
            user_id = self.get_user_id(response)
            if csrf and user_id:
                for st in self.searchterms:
                    yield Request(
                        url=self.SEARCH_URL.format(
                            offset=0, user_id=user_id, search_term=st,
                            store=self.store
                        ),
                        meta={
                            'search_term': st,
                            'remaining': self.quantity,
                            'csrf': csrf,
                            'headers': headers,
                            'user_id': user_id,
                            'current_page': 0
                        },
                        headers=headers
                    )
            else:
                self.log('Error while parsing the user_id and Token', WARNING)
        elif self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            headers['Accept'] = "application/vnd.mywebgrocer.product+json"

            sku = re.search('sku/(.*)', self.product_url)
            if sku:
                sku = sku.group(1)
            if self.store and sku and csrf:
                prod_url = self.PRODUCT_URL.format(store=self.store, sku=sku)
                yield Request(
                    url=prod_url,
                    callback=self._parse_single_product,
                    meta={"product": prod, 'search_term': '',
                          'remaining': self.quantity, 'csrf': csrf},
                    headers=headers
                )
            else:
                self.log('Error while parsing the Store and Sku, Token', WARNING)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        try:
            prod_data = json.loads(response.body)
        except:
            self.log(
                "Failed parsing json at {} - {}".format(response.url, traceback.format_exc())
                , WARNING)
            cond_set_value(product, "not_found", True)
            if not product.get('url'):
                cond_set_value(product, "url", self.product_url)
            return product

        reseller_id = self._parse_reseller_id(prod_data)
        cond_set_value(product, 'reseller_id', reseller_id)

        title = self._parse_title(prod_data)
        cond_set_value(product, 'title', title)

        is_out_of_stock = self._parse_out_of_stock(prod_data)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        brand = self._parse_brand(prod_data)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(prod_data)
        cond_set_value(product, 'image_url', image_url)

        self._parse_price(response, prod_data)

        product['locale'] = "en-US"

        description = self._parse_description(prod_data)
        product['description'] = description

        price_per_volume = self._parse_price_volume(prod_data)
        cond_set_value(product, 'price_per_volume', price_per_volume)

        volume_measure = self._parse_volume_measure(prod_data)
        cond_set_value(product, 'volume_measure', volume_measure)

        sku = prod_data.get('sku')
        cond_set_value(product, 'sku', sku)

        return product

    @staticmethod
    def _parse_reseller_id(data):
        id = data.get('Id')
        return str(id) if id else None

    def _parse_title(self, data):
        title = None
        try:
            title = data.get('Brand') + ' ' + data.get('Name')
        except:
            self.log('Error while parsing the Brand and Name'.format(traceback.format_exc()))
        return title

    @staticmethod
    def _parse_brand(data):
        return data.get('Brand')

    @staticmethod
    def _parse_description(data):
        return data.get('Description')

    @staticmethod
    def _parse_image_url(data):
        image = data.get('ImageLinks')
        if image:
            if len(image) > 3:
                image = image[2].get('Uri')
            else:
                image = image[-1].get('Uri')
        return image

    @staticmethod
    def _parse_price(response, data):
        product = response.meta['product']
        if data.get('CurrentPrice'):
            price = re.search('\d+\.\d*', data.get('CurrentPrice'))
            if price:
                cond_set_value(product, 'price',
                               Price(price=price.group(), priceCurrency='USD'))

    @staticmethod
    def _parse_out_of_stock(data):
        stock = data.get('InStock')
        return not(stock)

    @staticmethod
    def _parse_unit_price(data):
        return data.get('CurrentUnitPrice')

    def _parse_price_volume(self, data):
        unit_price = self._parse_unit_price(data)
        if unit_price.split('/'):
            price_volume = re.search(FLOATING_POINT_RGEX, unit_price.split('/')[0])
            return price_volume.group() if price_volume else None

    def _parse_volume_measure(self, data):
        unit_price = self._parse_unit_price(data)
        if len(unit_price.split('/')) > 1:
            volume_measure = unit_price.split('/')[1]
            return volume_measure if volume_measure else None

    def _scrape_total_matches(self, response):
        try:
            total_matches = int(json.loads(response.body).get('ItemCount'))
        except Exception as e:
            self.log("Invalid JSON for total matches {}".format(traceback.format_exc()))
            total_matches = 0

        return total_matches

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body)
            prods = data.get('Items')
        except:
            self.log("Failed parsing json at {} - {}".format(traceback.format_exc()))
            prods = []

        search_term = response.meta.get('search_term')
        csrf = response.meta.get('csrf')

        headers = response.meta.get('headers')
        headers['Accept'] = "application/vnd.mywebgrocer.product+json"

        prod_links = []
        for prod in prods:
            links = prod.get('Links', [])
            for data in links:
                if data.get('Rel') == "product.sku":
                    prod_links.append(data.get('Uri'))
        for link in prod_links:
            prod_item = SiteProductItem()
            req = Request(
                url=link,
                callback=self.parse_product,
                meta={
                    "product": prod_item,
                    'search_term': search_term,
                    'remaining': self.quantity,
                    'csrf': csrf
                },
                dont_filter=True,
                headers=headers
            )
            yield req, prod_item

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()

        user_id = meta.get('user_id')
        st = meta.get("search_term")
        current_page = meta.get('current_page')
        headers = meta.get('headers')

        headers['Accept'] = "application/vnd.mywebgrocer.grocery-list+json"
        meta['headers'] = headers

        totals = self._scrape_total_matches(response)

        current_page += 1
        meta['current_page'] = current_page

        offset = current_page * self.product_per_page
        if totals and offset >= totals:
            return

        return Request(
            url=self.SEARCH_URL.format(
                offset=offset, user_id=user_id, search_term=st,
                store=self.store
            ),
            meta=meta,
            dont_filter=True,
            headers=headers
        )

    def get_csrf(self, response):
        token = re.search('"Token":(.*?)",', response.body)
        return token.group(1).replace('\"', '').strip() if token else None

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    def get_user_id(self, response):
        user_id = re.search('"UserId":"(.*?)"', response.body)
        return user_id.group(1) if user_id else None