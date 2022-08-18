# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

from .gianteagle import GiantEagleProductsSpider
import json
from scrapy import Request
import traceback
import re

from product_ranking.items import SiteProductItem, Price
from product_ranking.utils import valid_url


class GiantEagleShelfPagesSpider(GiantEagleProductsSpider):
    name = 'gianteagle_shelf_urls_products'
    allowed_domains = ["www.gianteagle.com", "curbsideexpress.gianteagle.com"]

    CATEGORY_URL = 'https://curbsideexpress.gianteagle.com/api/product/v7/products/category/' \
                   '{category_id}/store/{p_storeid}?sort=Brand&skip={offset}&take=20&userId={user_id}'

    CATEGORY_SPECIAL_URL = 'https://curbsideexpress.gianteagle.com/api/product/v7/products/category/' \
                           '{category_id}/store/{p_storeid}?sort=Brand&skip={offset}&take=20&userId={user_id}' \
                           '&fq=Specials:All'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))
        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                          "Chrome/60.0.3112.78 Safari/537.36"
        self.product_json = None
        self.c_id = None
        self.user_id = None
        self.token = None
        self.p_store_id = None
        self.offset = None
        self.c_special_id = None

        super(GiantEagleShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      meta={'search_term': '', 'remaining': self.quantity},
                      callback=self._start_requests)

    def _start_requests(self, response):
        product_info = self._find_between(response.body, 'var configuration = ', '};')
        try:
            self.product_json = json.loads(product_info + '}')
            self.token = self.product_json.get('Token')
            category_id = re.search('category/(.*?)/', self.product_url).group(1)
            self.c_id = category_id.split(',')[-1]
            self.c_special_id = category_id.split(',')[0]
            self.user_id = self.product_json.get('CurrentUser', {}).get('UserId')
            self.p_store_id = self.product_json.get('PseudoStoreId')
            if self.c_special_id == '000':
                url = self.CATEGORY_SPECIAL_URL.format(user_id=self.user_id,
                                                       category_id=self.c_id,
                                                       p_storeid=self.p_store_id,
                                                       offset=0)
            else:
                url = self.CATEGORY_URL.format(user_id=self.user_id,
                                               category_id=self.c_id,
                                               p_storeid=self.p_store_id,
                                               offset=0)
        except:
            self.log("Error while parsing json data {}".format(traceback.format_exc()))

        return Request(url=url,
                       dont_filter=True,
                       headers={"Authorization": self.token,
                                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                                              "Chrome/60.0.3112.78 Safari/537.36",
                                "Accept": "application/vnd.mywebgrocer.grocery-list+json"},
                       meta=response.meta)

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body)
            totals = data['ItemCount']
            return totals
        except:
            self.log("Found no total matches {}".format(traceback.format_exc()))

    def _scrape_product_links(self, response):
        """
        Scraping product links from shelf page
        """
        try:
            data = json.loads(response.body)
            items = data['Items']
            for item in items:
                product = SiteProductItem()
                product['title'] = item['Name']
                product['sku'] = item['Sku']
                product['url'] = self.product_url.split('#')[0] + '#/product/sku/%s' % product['sku']
                product['brand'] = item['Brand']
                product['description'] = item['Description']

                currency = "USD"
                price = item['CurrentPrice'].replace("$", '')
                price = re.search('\d+\.?\d+', price).group()

                product['price'] = Price(price=float(price),
                                         priceCurrency=currency)
                product['is_out_of_stock'] = not bool(item['InStock'])
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
        if self.current_page >= self.num_pages:
            return

        self.current_page += 1

        if self.current_page > response.meta['total_matches'] / 20 + 1:
            return
        try:
            self.user_id = self.product_json.get('CurrentUser', {}).get('UserId')
            self.token = self.product_json.get('Token')
            self.p_store_id = self.product_json.get('PseudoStoreId')
            self.offset = (self.current_page - 1) * 20
            if self.c_special_id == '000':
                url = self.CATEGORY_SPECIAL_URL.format(user_id=self.user_id,
                                                       category_id=self.c_id,
                                                       p_storeid=self.p_store_id,
                                                       offset=self.offset)
            else:
                url = self.CATEGORY_URL.format(user_id=self.user_id,
                                               category_id=self.c_id,
                                               p_storeid=self.p_store_id,
                                               offset=self.offset)
        except:
            self.log("Error while paring json data {}".format(traceback.format_exc()))

        return Request(url=url,
                       dont_filter=True,
                       headers={"Authorization": self.token,
                                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                                              "Chrome/60.0.3112.78 Safari/537.36",
                                "Accept": "application/vnd.mywebgrocer.grocery-list+json"},
                       meta=response.meta)

    @staticmethod
    def _find_between(s, first, last, offset=0):
        try:
            s = s.decode("utf-8")
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""