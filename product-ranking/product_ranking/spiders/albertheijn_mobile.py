# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import re
import urllib
import json
import traceback

from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider
from product_ranking.spiders import cond_set_value
from scrapy.log import DEBUG, WARNING
from scrapy import Request


class AlbertHeijnProductsSpider(BaseProductsSpider):
    name = 'albertheijn_mobile_products'
    allowed_domains = ["www.ah.nl"]

    API_URL = "https://www.ah.nl/service/rest/delegate?url={url}"
    SEARCH_URL = "https://www.ah.nl/service/rest/delegate?url=/zoeken?" \
                 "rq={search_term}&searchType=product"

    header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) '
                            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36'}
    current_page = 0

    def __init__(self, *args, **kwargs):
        super(AlbertHeijnProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def start_requests(self):
        for st in self.searchterms:
            yield Request(url=self.SEARCH_URL.format(search_term=urllib.quote_plus(st.encode('utf-8'))),
                          meta={'search_term': st, 'remaining': self.quantity}, dont_filter=True)

        if self.product_url:
            product = SiteProductItem()
            product['is_single_result'] = True
            product['search_term'] = ''
            url = self.product_url.split('https://www.ah.nl')[1]
            yield Request(self.API_URL.format(url=url),
                          self._parse_single_product,
                          dont_filter=True, meta={'product': product})

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']
        data = []

        product_json = json.loads(response.body_as_unicode())
        for result in product_json.get('_embedded').get('lanes', []):
            if "ProductDetailLane" in result['type']:
                data = result.get('_embedded').get('items')[0].get('_embedded').get('product')

        if data:
            # Parse brand
            brand = data.get('brandName')
            cond_set_value(product, 'brand', brand)

            # Parse title
            if data.get('images', {}):
                title = data.get('images', {})[0].get('title')
                cond_set_value(product, 'title', title)

            # Parse out of stock
            is_out_of_stock = not data.get('availability', {}).get('orderable')
            cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

            # Parse price
            price = data.get('priceLabel', {}).get('now')

            cond_set_value(product, 'price', Price(
                    price=float(price),
                    priceCurrency="EUR"
                )) if price else None

            # Parse image url
            image_urls = data.get('images', {})
            if image_urls:
                image = max(image_urls, key=lambda x: x.get('height'))
                image_url = image.get('link', {}).get('href')
                cond_set_value(product, 'image_url', image_url)

            # Parse url
            if product_json.get('_links', {}).get('self', {}).get('href'):
                url = 'https://www.ah.nl%s' % product_json.get('_links', {}).get('self', {}).get('href')
                cond_set_value(product, 'url', url)

            # Parse categories
            categories = data.get('categoryName').split(',')
            cond_set_value(product, 'categories', categories)

            cond_set_value(product, 'department', categories[-1]) if categories else None

        return product

    def _scrape_total_matches(self, response):
        total = re.search('"ns_search_result":(.*?),', response.body_as_unicode(), re.DOTALL)
        try:
            total = int(total.group(1).replace('"', '')) if total else 0
        except Exception as e:
            self.log("Exception converting total_matches to int: {}".format(traceback.format_exc()), DEBUG)
            total = 0
        finally:
            return total

    def _scrape_results_per_page(self, response):
        item_count = 0
        try:
            lanes = json.loads(response.body_as_unicode()).get('_embedded').get('lanes')
            for lane in lanes:
                if lane.get('type') == 'LoadMoreLane':
                    item_count = re.search('(\d+) van', lane.get('title')).group(1)
        except:
            self.log('Invalid JSON: {}').format(traceback.format_exc(), WARNING)
            item_count = 0

        return int(item_count)

    def _scrape_product_links(self, response):
        try:
            json_data = json.loads(response.body_as_unicode())
            for result in json_data.get('_embedded').get('lanes', []):
                if "SearchLane" in result['type']:
                    links = result.get("_embedded").get("items", [])

            for link in [item for item in links if item.get('type') == "Product"]:
                url = link.get("navItem", {}).get("link", {}).get("href")
                prod_url = self.API_URL.format(url=url)
                yield prod_url, SiteProductItem()
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()))

    def _scrape_next_results_page_link(self, response):
        next_link = ''
        try:
            lanes = json.loads(response.body_as_unicode()).get('_embedded').get('lanes')
            for lane in lanes:
                if lane.get('type') == 'LoadMoreLane':
                    next_link = lane.get('navItem').get('link').get('href')
                    next_link = 'https://www.ah.nl%s' % next_link
        except:
            self.log('Invalid JSON: {}').format(traceback.format_exc(), WARNING)
            next_link = None

        return next_link