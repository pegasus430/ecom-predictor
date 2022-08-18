# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string

from scrapy.conf import settings
from scrapy import Request
import json
import traceback

from product_ranking.items import (SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator
from HTMLParser import HTMLParser


class GiantEagleProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'gianteagle_products'
    allowed_domains = ["curbsideexpress.gianteagle.com"]

    SEARCH_URL = 'https://curbsideexpress.gianteagle.com/store/C9CC1102/#/search/{search_term}'
    SEARCH_API_URL = "https://curbsideexpress.gianteagle.com/api/product/v7/products/store/{store_id}" \
                     "/search?skip={offset}&take=20&userId={user_id}&q={search_term}"

    PRODUCT_URL = "https://curbsideexpress.gianteagle.com/api/product/v7" \
                  "/product/store/{store_id}/sku/{sku}"

    PRODUCT_URL_PRETTY = "https://curbsideexpress.gianteagle.com/store/{store_id}/#/product/sku/{sku}"

    def __init__(self, *args, **kwargs):
        super(GiantEagleProductsSpider, self).__init__(site_name=self.allowed_domains[0],
                                                       *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                          "Chrome/65.0.3325.181 Safari/537.36"
        self.current_page = 1
        self.product_json = None

    def start_requests(self):
        for request in super(GiantEagleProductsSpider, self).start_requests():
            request = request.replace(callback=self._start_requests)
            yield request

    def _start_requests(self, response):
        product_info = self._find_between(response.body, 'var configuration = ', '};')
        try:
            self.product_json = json.loads(product_info + '}')
            self.token = self.product_json.get('Token')
            self.user_id = self.product_json.get('CurrentUser', {}).get('UserId')
            self.store_id = self.product_json.get('PseudoStoreId')
            if self.product_url:
                prod = SiteProductItem()
                prod['is_single_result'] = True
                prod['url'] = self.product_url
                prod['search_term'] = ''
                sku = re.search('sku/(.*)', self.product_url).group(1)
                return Request(url=self.PRODUCT_URL.format(store_id=self.store_id,
                                                           sku=sku),
                               dont_filter=True,
                               headers={"Authorization": self.token,
                                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                                                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                                                      "Chrome/61.0.3163.79 Safari/537.36",
                                        "Accept": "application/vnd.mywebgrocer.product+json"},
                               callback=self.parse_product,
                               meta={'product': prod})
            else:
                url = self.SEARCH_API_URL.format(user_id=self.user_id,
                                                 store_id=self.store_id,
                                                 search_term=response.meta['search_term'],
                                                 offset=0)
                return Request(url=url,
                               dont_filter=True,
                               headers={"Authorization": self.token,
                                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                                                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                                                      "Chrome/60.0.3112.78 Safari/537.36",
                                        "Accept": "application/vnd.mywebgrocer.grocery-list+json"},
                               meta=response.meta)
        except:
            self.log("Error while parsing json data {}".format(traceback.format_exc()))

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        try:
            product_json = json.loads(response.body)
        except:
            self.log("Error parsing JSON", traceback.format_exc())
            return

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(product_json)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse price
        price = self._parse_price(product_json)
        cond_set_value(product, 'price', price)

        # Parse brand
        brand = self._parse_brand(product_json)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        is_out_of_stock = self._is_out_of_stock(product_json)
        product["is_out_of_stock"] = is_out_of_stock

        # Parse categories
        categories = self._parse_categories(product_json)
        cond_set_value(product, 'categories', categories)

        # Parse reseller_id
        reseller_id = self._parse_reseller_id(product_json)
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse image url
        image_url = self._parse_image_url(product_json)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        return product

    @staticmethod
    def _parse_title(product_json):
        title = product_json.get('Name')
        if title:
            return HTMLParser().unescape(title)

    @staticmethod
    def _parse_brand(product_json):
        brand = product_json.get('Brand')
        return brand

    @staticmethod
    def _parse_categories(product_json):
        categories_sel = product_json.get('Category')
        if categories_sel:
            categories = categories_sel.split(',')
            return categories

    @staticmethod
    def _parse_reseller_id(product_json):
        reseller_id = product_json.get('Sku')
        return reseller_id

    @staticmethod
    def _parse_image_url(product_json):
        image_links = product_json.get('ImageLinks')
        if image_links:
            for image_link in image_links:
                if image_link.get('Rel') == 'large':
                    return image_link.get('Uri')

    @staticmethod
    def _parse_price(product_json):
        currency = "USD"

        try:
            price = product_json.get('CurrentPrice').split(' ')[0]

            price = float(price.replace('$', ''))
            return Price(price=price, priceCurrency=currency)

        except:
            return None

    @staticmethod
    def _is_out_of_stock(product_json):
        try:
            out_of_stock = product_json.get('InStock')
            if not out_of_stock:
                return True
            return False
        except:
            return None

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body)
            totals = data['TotalQuantity']
            return totals
        except:
            self.log("Found no total matches {}".format(traceback.format_exc()))

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        try:
            data = json.loads(response.body)
            items = data['Items']
            for item in items:
                product = SiteProductItem()
                product['title'] = item['Name']
                product['sku'] = item['Sku']
                product['url'] = self.PRODUCT_URL_PRETTY.format(sku=product['sku'], store_id=self.store_id)
                product['brand'] = item['Brand']

                currency = "USD"
                price = item['CurrentPrice'].replace("$", '')
                price = re.search('\d+\.?\d+', price).group()

                product['price'] = Price(price=float(price),
                                         priceCurrency=currency)
                product['is_out_of_stock'] = not bool(item['InStock'])
                product['reseller_id'] = item['Sku']
                categories = item['Category'].split('/')
                product['categories'] = categories

                if categories:
                    product['department'] = categories[-1]

                for image in item['ImageLinks']:
                    if image['Rel'] == 'large':
                        product['image_url'] = image['Uri']

                yield None, product
        except:
            self.log("Error while parsing products {}".format(traceback.format_exc()))

    def _scrape_next_results_page_link(self, response):
        self.current_page += 1

        if self.current_page > response.meta['total_matches'] / 20 + 1:
            return
        try:
            user_id = self.product_json.get('CurrentUser', {}).get('UserId')
            token = self.product_json.get('Token')
            store_id = self.product_json.get('PseudoStoreId')
            offset = (self.current_page - 1) * 20
            url = self.SEARCH_API_URL.format(user_id=user_id,
                                             store_id=store_id,
                                             search_term=response.meta['search_term'],
                                             offset=offset)
            return Request(url=url,
                           dont_filter=True,
                           headers={"Authorization": token,
                                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                                  "Chrome/60.0.3112.78 Safari/537.36",
                                    "Accept": "application/vnd.mywebgrocer.grocery-list+json"},
                           meta=response.meta)
        except:
            self.log("Error while paring json data {}".format(traceback.format_exc()))

    @staticmethod
    def _find_between(s, first, last, offset=0):
        try:
            s = s.decode("utf-8")
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""
