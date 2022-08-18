# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import urlparse
import json
import traceback
import math

from scrapy.log import INFO
from scrapy.conf import settings
from scrapy import Request

from product_ranking.items import (SiteProductItem, BuyerReviews, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults


class LazadaProductsSpider(BaseProductsSpider):
    name = 'lazadasg_products'
    allowed_domains = ["lazada.sg"]

    SEARCH_URL = "https://www.lazada.sg/catalog/?ajax=true&page={page_num}&q={search_term}"

    def __init__(self, *args, **kwargs):
        url_formatter = FormatterWithDefaults(page_num=1)

        super(LazadaProductsSpider, self).__init__(url_formatter, site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        try:
            product_json = response.xpath('//script[@type="application/ld+json"]/text()')[0].extract()
            product_json = json.loads(product_json)
        except:
            self.log('JSON not found or invalid JSON: {}'.format(traceback.format_exc()))
            product['not_found'] = True
            return product

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = product_json.get('name')
        cond_set_value(product, 'title', title)

        # Parse brand
        brand = product_json.get('brand', {}).get('name')
        cond_set_value(product, 'brand', brand)

        # Parse sku
        sku = product_json.get('sku')
        cond_set_value(product, 'sku', sku)

        # Parse stock status
        is_out_of_stock = self._parse_out_of_stock(response, product_json)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse categories
        categories = self._parse_categories(response, product_json)
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse price
        price = self._parse_price(response, product_json)
        cond_set_value(product, 'price', price)

        # Parse reseller id
        reseller_id = product_json.get('sku')
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse image url
        image_url = product_json.get('image')
        cond_set_value(product, 'image_url', image_url)

        # Parse buyer reviews
        buyer_reviews = self._parse_buyer_reviews(response, product_json)
        cond_set_value(product, 'buyer_reviews', BuyerReviews(**buyer_reviews))

        return product

    @staticmethod
    def _parse_out_of_stock(response, product_json):
        stock_status = product_json.get('offers', {}).get('availability')
        if stock_status and 'InStock' in stock_status:
            return False
        return True

    @staticmethod
    def _parse_categories(response, product_json):
        categories_sel = product_json.get('category', '').split('>')
        categories = [i.strip() for i in categories_sel]
        return categories

    @staticmethod
    def _parse_price(response, product_json):
        currency = "SGD"
        price = product_json.get('offers', {}).get('price')
        if not price:
            price = product_json.get('offers', {}).get('lowPrice')
        if price:
            return Price(price=float(price), priceCurrency=currency)

    @staticmethod
    def _parse_buyer_reviews(response, product_json):
        rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        average_rating = product_json.get('aggregateRating', {}).get('ratingValue')
        num_of_reviews = product_json.get('aggregateRating', {}).get('ratingCount')

        reviews = response.xpath('//span[@class="c-rating-bar-list__count"]/text()').extract()

        if average_rating and num_of_reviews:
            for i, review in enumerate(reviews):
                rating_by_star[str(5 - i)] = int(review.strip())
            buyer_reviews = {
                'num_of_reviews': int(num_of_reviews),
                'average_rating': round(float(average_rating), 1),
                'rating_by_star': rating_by_star
            }

        else:
            buyer_reviews = ZERO_REVIEWS_VALUE

        return buyer_reviews

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            totals = data.get('mainInfo', {}).get('dataLayer', {}).get('page', {}).get('resultNr')
            return int(totals)
        except:
            self.log("Found no total matches {}".format(traceback.format_exc()))
            return 0

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        try:
            data = json.loads(response.body_as_unicode())
            items = data.get('mods', {}).get('listItems')
            for item in items:
                res_item = SiteProductItem()
                link = urlparse.urljoin(response.url, item.get('productUrl'))
                yield link, res_item
        except:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page')
        if not current_page:
            current_page = 1
        total_matches = response.meta.get('total_matches')
        results_per_page = self._scrape_results_per_page(response)
        if not results_per_page:
            results_per_page = 40
        if (total_matches and results_per_page
            and current_page < math.ceil(total_matches / float(results_per_page))):
            current_page += 1
            response.meta['current_page'] = current_page

            return Request(self.SEARCH_URL.format(search_term=response.meta['search_term'],
                                                  page_num=current_page),
                           meta=response.meta)
