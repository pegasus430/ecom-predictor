# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import traceback
import json
import socket
import re
import urllib
import time
import string

from scrapy.http import Request
from scrapy.conf import settings
from scrapy.log import WARNING

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import (SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults, cond_set_value
from product_ranking.validation import BaseValidator

class GoogleExpressProductsSpider(BaseValidator, BaseProductsSpider):

    name = 'google_express_products'
    allowed_domains = ["google.com"]

    HEADERS = {
        'content-type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest'
    }

    SEARCH_URL = "https://express.google.com/express/_/data?ds.extension=142508757&_egch=1&_reqid={req_id}&rt=j"

    def __init__(self, *args, **kwargs):
        url_formatter = FormatterWithDefaults(req_id='asdfasdf')
        super(GoogleExpressProductsSpider, self).__init__(
            url_formatter=url_formatter,
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)
        socket.setdefaulttimeout(60)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        settings.overrides['USE_PROXIES'] = True

        self.total_matches = None

    def start_requests(self):
        """Generate Requests from the SEARCH_URL and the search terms."""
        for request in super(GoogleExpressProductsSpider, self).start_requests():
            if not self.product_url:
                formdata = {
                    'f.req': '[[[142508757,[{'
                             + '"142508757":[null,"%s",null,null,1,"ALEfSmewwuEx2m_j6slcao2fE-iKZCTnvR5olGS9VEh'
                               'BwOpydsNhVJ5zsrsaDbHIQhd2arL3S_eyQFaB2g-Iv-Plxw_qCdLifn2EMu5yBqgxvuvK_RFnI_v0V'
                               '8bWAc6SxZbnEpx6XJvkwLNFYdipuCWC7mTrrZpoW2hw5M3UFn6NREfnNSpqNfL8DWknAV55s026iB6'
                               'B6Flz8L0KEx88clhnGVblpLKk4ZRq-6HuCHFAL0saEfjory8wgsB0-_Wa_nnrHkeX9ide",'
                               '"/search?q=%s"]'
                             + '}],null,null,0]]]',
                }

                st = request.meta['search_term']
                formdata_model = formdata.copy()
                formdata_model['f.req'] = formdata_model['f.req'] % ('', st)

                req_id = int(time.time())
                req_id = str(req_id)[3:]

                meta = request.meta
                meta['req_id'] = req_id
                meta['formdata'] = formdata
                meta['search_term'] = st

                request = Request(
                    url=self.SEARCH_URL.format(req_id=req_id),
                    method='POST',
                    body=urllib.urlencode(formdata_model),
                    meta=meta,
                    dont_filter=True,
                    headers=self.HEADERS
                )

            yield request

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']
        # Set locale
        product['locale'] = 'en_US'

        data = re.search("hash: '4', data:function\(\){return(.*?)}}\);</script>",
                        response.body, re.DOTALL)
        try:
            data = json.loads(data.group(1))

            # Parse title
            title = self._parse_title(data)
            cond_set_value(product, 'title', title, conv=string.strip)

            # Parse brand
            product['brand'] = guess_brand_from_first_words(title)

            # Parse image url
            image_url = self._parse_image_url(data)
            cond_set_value(product, 'image_url', image_url, conv=string.strip)

            # Parse categories
            categories = self._parse_categories(data)
            cond_set_value(product, 'categories', categories)

            # Parse price
            price = self._parse_price(data)
            cond_set_value(product, 'price', price)

            # Parse buyer_reviews
            buyer_reviews = self._parse_buyer_reviews(data)
            cond_set_value(product, 'buyer_reviews', buyer_reviews)

        except:
            self.log('Error parsing product json: {}'.format(traceback.format_exc()))

        return product

    def _parse_single_product(self, response):
        return self.parse_product(response)

    @staticmethod
    def _parse_title(data):
        try:
            title = data[1][1][1][0][17][0][1]
        except:
            print 'Error while parsing title'
            title = None
        return title

    @staticmethod
    def _parse_image_url(data):
        try:
            image = data[1][1][1][0][48][1][0][0]
        except:
            print 'Error while parsing image url'
            image = None
        return image

    @staticmethod
    def _parse_categories(data):
        try:
            categories = []
            category_list = data[1][1][1][0][17][0][3].split('>')
            for cat in category_list:
                categories.append(cat.strip())
        except:
            print 'Error while parsing categories'
            categories = None
        return categories

    @staticmethod
    def _parse_price(data):
        try:
            price = data[1][1][1][0][48][11][2][1]
            return Price(price=price.replace('$', ''), priceCurrency='USD')
        except:
            print 'Error while parsing price'
            pass

    @staticmethod
    def _parse_buyer_reviews(data):
        try:
            length = len(data[1][1][1])
            review_data = data[1][1][1][length-2]
            review_count = review_data[11][0][1]
            average_rating = review_data[11][0][2]

            rating_by_stars = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}

            for i in range(0, 5):
                rating_by_stars[str(5 - i)] = review_data[11][0][3][i][1]

            buyer_reviews = {
                'num_of_reviews': review_count,
                'average_rating': round(float(average_rating), 1) if average_rating else 0,
                'rating_by_star': rating_by_stars
            }
        except:
            print 'Error while parsing buyer reviews'
            buyer_reviews = None
        return buyer_reviews

    def _scrape_total_matches(self, response):
        total_matches = re.search('"(.*?) results"', response.body)
        try:
            self.total_matches = int(total_matches.group(1).replace('+', '').replace(',', ''))
            return self.total_matches
        except:
            self.log('Error parsing total matches{}'.format(traceback.format_exc()))

    def _scrape_product_links(self, response):
        links = re.findall('"product/(.*?)"', response.body)
        for link in links:
            item = SiteProductItem()
            link = 'https://express.google.com/product/' + link
            yield link, item

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        st = meta.get('search_term')
        cat_id = meta.get('cat_id')
        cat_id = st or cat_id
        formdata = meta.get('formdata').copy()

        req_id = str(int(meta['req_id']) + 1000000)
        meta['req_id'] = req_id

        current_page = meta.get('current_page', 1)

        if current_page * 30 > self.total_matches:
            return
        meta['current_page'] = current_page + 1
        page_token = None

        try:
            start = response.body_as_unicode().index('[')
            content = json.loads(response.body[start:])
            page_token = content[0][0][2]['142508757'][2]
            formdata['f.req'] = formdata['f.req'] % (page_token, cat_id)
        except:
            self.log('Error while parsing the json data'.format(traceback.format_exc()))

        if page_token:
            return Request(
                        url=self.SEARCH_URL.format(req_id=req_id),
                        method='POST',
                        body=urllib.urlencode(formdata),
                        meta=meta,
                        dont_filter=True,
                        headers=self.HEADERS
                    )
        else:
            self.log('Error with page token', WARNING)

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t]", "", text).strip()