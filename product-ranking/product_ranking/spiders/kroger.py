# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, unicode_literals

import urllib
import re
import json
import traceback

from scrapy import Request
from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.utils import SharedCookies
from scrapy.conf import settings

from scrapy.log import ERROR, WARNING


class KrogerProductsSpider(BaseProductsSpider):
    name = 'kroger_products'
    allowed_domains = ['kroger.com']

    AUTH_URL = 'https://www.kroger.com/auth/api/sign-in'

    CHECK_COOKIES_URL = 'https://www.kroger.com/storecatalog/clicklistbeta/#/'

    STORE_SEARCH_URL = 'https://www.kroger.com/stores/api/graphql'

    SEARCH_URL = 'https://www.kroger.com/search/api/searchAll?start={start}&count={count}&query={search_term}&tab=0'

    SEARCH_SORT = {
        'default': 'popularity',
        'popularity': 'popularity',
        'name': 'name'
    }
    PAGE_SIZE = 24

    PRODUCT_URL = 'https://www.kroger.com/products/api/products/details'

    use_proxies = False  # TOR is blocked, requires USA ip

    def __init__(self, disable_shared_cookies=True, *args, **kwargs):
        self.email = kwargs.get('email', 'ankur@contentanalytics.com')
        self.password = kwargs.get('password', 'Cai.2014')
        self.zip_code = kwargs.get('zip_code', '45209')

        super(KrogerProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                category_id='',
                start=0,
                count=self.PAGE_SIZE
            ),
            *args,
            **kwargs)

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        settings.overrides['USER_AGENT'] = 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'
        self.shared_cookies = SharedCookies('kroger') if not disable_shared_cookies else None

    def _get_antiban_headers(self):
        return {
            'Content-Type': 'application/json;charset=utf-8',
            'User-Agent': 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'
        }

    def start_requests(self):
        cookies = self.shared_cookies.get() if self.shared_cookies else None

        if cookies:
            yield Request(self.CHECK_COOKIES_URL,
                          callback=self._check_cookies,
                          dont_filter=True,
                          headers=self._get_antiban_headers())
        else:
            # start of authorization
            if self.shared_cookies:
                self.shared_cookies.lock()

            auth_data = {
                'account': {
                    'email': self.email,
                    'password': self.password,
                    'rememberMe': True
                },
                'location': ''
            }

            yield Request(self.AUTH_URL,
                          method='POST',
                          body=json.dumps(auth_data),
                          callback=self._search_store,
                          headers=self._get_antiban_headers(),
                          )

    def _check_cookies(self, response):
        auth_form = response.xpath(".//form[@id='signInForm']")

        if auth_form:
            # wrong cookies
            self.log('Cookies are expired. Start authorization', WARNING)
            self.shared_cookies.delete()

            for item in self.start_requests():
                yield item
        else:
            # skip authorization
            for item in self._start_requests(None):
                yield item

    def _search_store(self, response):
        data = {
            "query": "\n      query dropdownStoreSearch($searchText: String!) " \
                     "{\n        dropdownStoreSearch(searchText: $searchText) " \
                     "{\n          divisionNumber\n          vanityName\n     " \
                     "     storeNumber\n          phoneNumber\n          " \
                     "showShopThisStoreAndPreferredStoreButtons\n          " \
                     "distance\n          address {\n            addressLine1\n" \
                     "            addressLine2\n            city\n            countryCode\n" \
                     "            stateCode\n            zip\n          }\n          " \
                     "formattedHours {\n            displayName\n            displayHours" \
                     "\n            isToday\n          }\n          departments " \
                     "{\n            code\n          }\n        }\n      }",
            "variables": {
                'searchText': self.zip_code,
                'filters': '[]'
            },
            "operationName": "dropdownStoreSearch"
        }
        yield Request(
            self.STORE_SEARCH_URL,
            method='POST',
            callback=self._pick_store,
            body=json.dumps(data),
            headers=self._get_antiban_headers()
        )

    def _pick_store(self, response):
        try:
            stores = json.loads(response.body)

            if stores:
                store = stores.get('data', {}).get('dropdownStoreSearch', [{}])[0]

                data = {
                    "query": "\n    query storeById($divisionNumber: String!, $storeNumber: String!) {\n      "
                             "storeById(divisionNumber: $divisionNumber, storeNumber: $storeNumber) {\n        "
                             "divisionNumber\n        storeNumber\n        vanityName\n        phoneNumber\n        "
                             "latitude\n        longitude\n        brand\n        localName\n        address {\n"
                             "          addressLine1\n          city\n          stateCode\n          zip\n        }\n"
                             "        pharmacy {\n          phoneNumber\n          formattedHours {\n            "
                             "displayName\n            displayHours\n            isToday\n          }\n        }\n"
                             "        formattedHours {\n          displayName\n          displayHours\n          "
                             "isToday\n        }\n        departments {\n          friendlyName\n          "
                             "code\n        }\n        onlineServices {\n          name\n          url\n        }\n"
                             "        fulfillmentMethods {\n          hasPickup\n          hasDelivery\n        }\n"
                             "      }\n    }",
                    "variables": {
                        "storeNumber": store.get('storeNumber'),
                        "divisionNumber": store.get('divisionNumber')
                    },
                    "operationName": "storeById"
                }

                address = store.get('address', {})
                cookies = {
                    "bypassUnsupportedBrowser": True,
                    "DivisionID": store.get('divisionNumber'),
                    "StoreZipCode": store.get('address', {}).get('zip'),
                    "StoreCode": store.get('storeNumber'),
                    "StoreLocalName": "Kroger",
                    "StoreAddress": "{}, {}, {}".format(address.get('addressLine1'), address.get('city'),
                                                        address.get('stateCode'))

                }
                response.meta.update({'store_cookies': cookies})

                yield Request(self.STORE_SEARCH_URL,
                              method='POST',
                              body=json.dumps(data),
                              callback=self._start_requests,
                              headers=self._get_antiban_headers(),
                              cookies=cookies,
                              meta=response.meta,
                              dont_filter=True)
            else:
                self.log('Stores near zip {} not found'.format(self.zip_code), ERROR)
        except Exception:
            self.log(traceback.format_exc(), ERROR)

    def _start_requests(self, response):
        # end of authorization
        if self.shared_cookies:
            self.shared_cookies.unlock()

        for item in super(KrogerProductsSpider, self).start_requests():
            item.headers.update(self._get_antiban_headers())
            item = item.replace(method="POST")
            item.cookies.update(response.meta['store_cookies'])
            if self.searchterms:
                item.headers.update({'content-length': '0'})
            else:
                match = re.search(r'/(\d+)', item.url)
                if match:
                    item = item.replace(url=self.PRODUCT_URL, body=json.dumps({"upcs": [match.group(1)]}))
                else:
                    self.log('UPC not found in url: {}'.format(item.url), WARNING)
                    return
            yield item

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body)
            upcs = data.get('upcs', [])
            for upc in upcs:
                item = SiteProductItem()
                yield Request(self.PRODUCT_URL, method="POST",
                              dont_filter=True,
                              headers=self._get_antiban_headers(),
                              callback=self._parse_single_product,
                              cookies=response.request.cookies,
                              body=json.dumps({"upcs": [upc]}),
                              meta={"product": item}), item
        except:
            self.log("Failed to parse product links: {}".format(traceback.format_exc()))

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body)
            return data.get('productsInfo', {}).get('totalCount', 0)
        except:
            self.log("Failed to parse total count: {}".format(traceback.format_exc()), ERROR)

    def _scrape_results_per_page(self, response):
        try:
            data = json.loads(response.body)
            upcs = data.get('upcs', [])
            return len(upcs)
        except:
            self.log("Failed to extract results per page amount")
            return self.PAGE_SIZE

    def _scrape_next_results_page_link(self, response):
        try:
            data = json.loads(response.body)

            start = response.meta.get('start', 0)

            if start + self.PAGE_SIZE < data.get('productsInfo', {}).get('totalCount', 0):
                start += self.PAGE_SIZE

                next_page = self.url_formatter.format(
                    self.SEARCH_URL,
                    start=start,
                    search_term=urllib.quote_plus(response.meta['search_term'].encode('utf-8')),
                    count=self.PAGE_SIZE
                )
                response.meta['start'] = start

                return response.request.replace(url=next_page, meta=response.meta)
        except Exception:
            self.log("Failed to scrape next page link: {}".format(traceback.format_exc()), ERROR)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        try:
            data = json.loads(response.body)
            if not data.get('products'):
                product['available_store'] = False
                product['is_out_of_stock'] = True
                self.log("Sorry, this item is not currently available at your store.")
                return product
            data = data['products'][0]
        except:
            self.log("Failed to parse product: {}".format(traceback.format_exc()))
        else:
            for key, value in self._parse_product_data(data).iteritems():
                product[key] = value
        finally:
            return product

    def _parse_product_data(self, data):
        product_data = {
            'title': data.get('description'),
            'upc': data.get('upc'),
            'sku': data.get('upc'),
            'url': 'https://www.kroger.com/p/{slug}/{upc}'.format(slug=data.get('slug'),
                                                                  upc=data.get('upc')),
            'image_url': data.get('mainImage'),
            'price': self._parse_price(data),
            'is_out_of_stock': False,
            'in_store_pickup': bool(data.get('soldInStore')),
            'brand': data.get('brandName') or guess_brand_from_first_words(data.get('description', '')),
            'reseller_id': data.get('upc')
        }

        return product_data

    def _parse_price(self, data):
        try:
            raw_price = data.get('priceSale') or data.get('priceNormal')
            price = float(raw_price.replace(',', ''))
        except:
            self.log("Failed to parse price: {}".format(traceback.format_exc()))
            price = 0.00
        return Price(priceCurrency='USD', price=price)
