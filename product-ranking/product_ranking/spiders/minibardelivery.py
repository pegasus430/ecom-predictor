# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import urllib
import re

import traceback
import json
import socket

from scrapy import Request
from scrapy.log import INFO, WARNING, DEBUG
from scrapy.conf import settings

from product_ranking.items import (SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty


class MinibarDeliveryProductsSpider(BaseValidator, BaseProductsSpider):

    name = 'minibardelivery_products'
    allowed_domains = ["minibardelivery.com"]

    SEARCH_URL = "https://minibardelivery.com/api/v2/supplier/{supplier_ids}/product_groupings?" \
                 "page={page_num}&" \
                 "per_page=15&" \
                 "query={search_term}&" \
                 "tag=&type=&brand=&facet_list[]=hierarchy_type&" \
                 "facet_list[]=hierarchy_subtype&sort=popularity&" \
                 "sort_direction=desc&category=&hierarchy_category=&" \
                 "exclude_previous=false&only_previous=false&recommended=false"

    STREET_ADDRESS = '400 Brannan Street, San Francisco CA 94117'

    HOME_URL = 'https://minibardelivery.com'

    SUPPLIERS_URL = 'https://minibardelivery.com/api/v2/suppliers?address_id=&coords[latitude]=37.7800851' \
                    '&coords[longitude]=-122.39460170000001&address[address1]=400 Brannan Street' \
                    '&address[city]=San Francisco&address[state]=CA&address[zip_code]=94107' \
                    '&routing_options[defer_load]=true&defer_load=true'

    API_URL = "https://minibardelivery.com/api/v2/supplier/{supplier_ids}/product_grouping/{title_link}"

    API_V2_URL = "https://minibardelivery.com/api/v2/product_grouping/{title_link}?supplier_ids[]=_{supplier_ids}"

    user_agent = 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'

    HEADER = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'User-Agent': user_agent,
        'X-Requested-With': 'XMLHttpRequest'
    }

    result_per_page = 15

    def __init__(self, *args, **kwargs):
        super(MinibarDeliveryProductsSpider, self).__init__(site_name=self.allowed_domains[0],
                                                            *args, **kwargs)

        socket.setdefaulttimeout(60)

        settings.overrides['USE_PROXIES'] = True
        retry_codes = settings.get('RETRY_HTTP_CODES')
        retry_codes += [503]
        settings.overrides['RETRY_HTTP_CODES'] = retry_codes

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

        self.total_matches = None
        self.current_page = 1

    def start_requests(self):
        home_req_headers = {
            ':authority': 'minibardelivery.com',
            ':method': 'GET',
            ':path': '/',
            ':scheme': 'https',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'User-Agent': self.user_agent,
            'upgrade-insecure-requests': '1'
        }

        yield Request(
            url=self.HOME_URL,
            dont_filter=True,
            callback=self.start_requests_with_csrf,
            headers=home_req_headers
        )

    def start_requests_with_csrf(self, response):
        csrf = self.get_csrf(response)

        self.HEADER.setdefault('Authorization', csrf)

        if csrf:
            yield Request(
                url=self.SUPPLIERS_URL,
                dont_filter=True,
                headers=self.HEADER,
                callback=self._start_requests,
            )
        else:
            self.log("Failed Parsing CSRF", WARNING)

    def _start_requests(self, response):
        try:
            ids = []
            suppliers = json.loads(response.body)['suppliers']
            for supplier in suppliers:
                ids.append(str(supplier['id']))
            ids = ','.join(ids)

            if not self.product_url:
                for st in self.searchterms:
                    yield Request(
                        self.url_formatter.format(
                            self.SEARCH_URL,
                            search_term=urllib.quote_plus(st.encode('utf-8').replace(' ', '-')),
                            supplier_ids=ids,
                            page_num=self.current_page,
                        ),
                        meta={'search_term': st, 'remaining': self.quantity, 'supplier_ids': ids},
                        headers=self.HEADER,
                    )

            elif self.product_url:
                prod = SiteProductItem()
                prod['is_single_result'] = True
                prod['url'] = self.product_url
                prod['search_term'] = ''

                yield Request(
                    url=self.product_url,
                    meta={
                        "product": prod,
                        'search_term': "",
                        'remaining': self.quantity,
                        'ids': ids
                    },
                    dont_filter=True,
                    callback=self._parse_single_product
                )
        except Exception as e:
            self.log("Failed Parsing suppliers {}".format(traceback.format_exc(e)))

    def parse_product(self, response):
        meta = response.meta
        product = meta.get('product')
        ids = response.meta.get('ids')
        # Set locale
        product['locale'] = 'en_US'

        title_link = is_empty(response.xpath('//div[@class="row"]/@data-product-permalink').extract())
        if not title_link:
            inline_json = self._extract_inline_json(response)
            title_link = inline_json.get('permalink')

        if title_link:
            meta.update({
                'title_link': title_link,
                'supplier_ids': ids,
            })
            return Request(self.API_URL.format(supplier_ids=ids, title_link=title_link),
                           dont_filter=True,
                           meta=meta,
                           headers=self.HEADER,
                           callback=self._parse_product_json)

        return product

    def _extract_inline_json(self, response):
        inline_json = {}
        try:
            inline_json = json.loads(re.search(r'Store.ExternalProductData =(.*?});', response.body).group(1))
        except:
            self.log("Error while parsing inline json data: {}".format(traceback.format_exc()), WARNING)

        return inline_json

    def _parse_product_json(self, response):
        meta = response.meta
        product = meta.get('product')
        try:
            data = json.loads(response.body_as_unicode())
            product['title'] = data.get('name')
            product['brand'] = data.get('brand')
            product['department'] = data.get('category')
            product['image_url'] = data.get('image_url')
            product['description'] = data.get('description')

            price = is_empty(data.get('variants'))
            if price and price.get('price'):
                product['price'] = Price(price=price.get('price'), priceCurrency='USD')

            out_of_stock_status = True

            variants = []
            v_items = data.get('variants')
            for item in v_items:
                variant = {}
                variant['id'] = item.get('id')
                variant['price'] = item.get('price')
                variant['image_url'] = item.get('image_url')
                if item.get('in_stock') > 0:
                    variant['is_out_of_stock'] = False
                    out_of_stock_status = False
                else:
                    variant['is_out_of_stock'] = True
                variants.append(variant)

            product['variants'] = variants
            product['is_out_of_stock'] = out_of_stock_status

        except:
            self.log("Error while parsing json data: {}".format(traceback.format_exc()), WARNING)

        if not product.get('price'):
            title_link = meta.get('title_link')
            ids = meta.get('supplier_ids')
            meta['product'] = product

            return Request(self.API_V2_URL.format(supplier_ids=ids, title_link=title_link),
                           dont_filter=True,
                           meta=meta,
                           headers=self.HEADER,
                           callback=self._parse_price_alternate)

        return product

    def _parse_price_alternate(self, response):
        meta = response.meta
        product = meta.get('product')

        try:
            data = json.loads(response.body_as_unicode())
            price = is_empty(data.get('external_products'))
            if price and price.get('min_price'):
                product['price'] = Price(price=price.get('min_price'), priceCurrency='USD')
        except:
            self.log("Error while parsing price alternate: {}".format(traceback.format_exc()), WARNING)

        return product

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body)
            self.total_matches = data.get('count')
        except Exception as e:
            self.log("Exception looking for total_matches {}".format(e), DEBUG)
            self.total_matches = 0

        return self.total_matches

    def _scrape_product_links(self, response):
        url_head = 'https://minibardelivery.com/store/product/'
        ids = response.meta.get('supplier_ids')
        try:
            data = json.loads(response.body)
            links = data.get('product_groupings')
            for link in links:
                res_item = SiteProductItem()
                req = Request(
                    url=url_head + link.get('permalink'),
                    callback=self.parse_product,
                    dont_filter=True,  # some items redirect to the same 404 page
                    meta={'product': res_item, 'ids': ids}
                )
                yield req, res_item
        except:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        ids = response.meta.get('supplier_ids')

        if self.current_page * self.result_per_page > self.total_matches:
            return

        self.current_page += 1
        st = response.meta['search_term']

        url = self.SEARCH_URL.format(page_num=self.current_page, search_term=st, supplier_ids=ids)
        return Request(
            url,
            headers=self.HEADER,
            dont_filter=True,
            meta={
                'search_term': st,
                'remaining': self.quantity,
                'supplier_ids': ids
            },
        )

    def get_csrf(self, response):
        csrf = response.xpath("//meta[@name='access-token']/@content").extract()
        return ' '.join(['bearer', csrf[0]]) if csrf else None

    def _get_products(self, response):
        if response.meta.get('products_per_page') is None:
            response.meta['products_per_page'] = self._scrape_total_matches(response)

        for item in super(MinibarDeliveryProductsSpider, self)._get_products(response):
            yield item
