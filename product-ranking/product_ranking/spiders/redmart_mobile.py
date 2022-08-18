# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import json
import traceback
import math

from scrapy.log import INFO, WARNING
from scrapy import Request
from scrapy.conf import settings

from product_ranking.items import (SiteProductItem, Price, BuyerReviews)
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults


class RedmartMobileProductsSpider(BaseProductsSpider):
    name = 'redmart_mobile_products'
    allowed_domains = ["redmart.com"]

    SEARCH_URL = "https://api.redmart.com/v1.6.0/catalog/search?page={page_num}" \
                 "&pageSize=30&sort=1024&q={search_term}"
    PRODUCT_API_URL = "https://api.redmart.com/v1.6.0/catalog/products/{}" \
                      "?mixNmatch=true&pageSize=18&sameBrand=true&similarProduct=true"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
                 "passkey=3aqde2lhhpwod1c1ve03mx30j" \
                 "&apiversion=5.5" \
                 "&displaycode=13815-en_sg" \
                 "&resource.q0=products" \
                 "&filter.q0=id:eq:{}" \
                 "&stats.q0=reviews"

    def __init__(self, *args, **kwargs):
        url_formatter = FormatterWithDefaults(page_num=0)
        super(RedmartMobileProductsSpider, self).__init__(url_formatter, *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        for request in super(RedmartMobileProductsSpider, self).start_requests():
            if self.product_url:
                prod = SiteProductItem()
                prod['is_single_result'] = True
                prod['url'] = self.product_url
                prod['search_term'] = ''
                product_name = re.search('product/(.*)', self.product_url)
                if product_name:
                    request = request.replace(url=self.PRODUCT_API_URL.format(product_name.group(1)),
                                              callback=self._parse_single_product,
                                              meta={'product': prod},
                                              dont_filter=True)
            yield request

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        try:
            product_json = json.loads(response.body_as_unicode())
            product_json = product_json.get('product')
        except:
            self.log("JSON Error {}".format(traceback.format_exc()))
            product['not_found'] = True
            return product

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = product_json.get('title')
        cond_set_value(product, 'title', title)

        # Parse brand
        brand = product_json.get('filters', {}).get('brand_name')
        cond_set_value(product, 'brand', brand)

        # Parse sku
        sku = product_json.get('sku')
        cond_set_value(product, 'sku', sku)

        # Parse price
        price = self._parse_price(response, product_json)
        cond_set_value(product, 'price', price)

        # Parse stock status
        is_out_of_stock = self._parse_is_out_of_stock(response, product_json)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse image url
        image_url = self._parse_image_url(response, product_json)
        cond_set_value(product, 'image_url', image_url)

        # Parse reseller_id
        reseller_id = self._parse_reseller_id(product.get("url"))
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse was_now
        was_now = self._parse_was_now(response, product_json)
        product['was_now'] = was_now

        # Parse origin
        origin = self._parse_origin(response, product_json)
        product['origin'] = origin

        if was_now:
            product['promotions'] = bool(was_now)

        product_id = product_json.get('id')
        if product_id:
            url = self.REVIEW_URL.format(product_id)
            return Request(
                url=url,
                callback=self._parse_buyer_reviews,
                meta={'product': product},
                dont_filter=True
            )

        return product

    @staticmethod
    def _parse_reseller_id(url):
        reseller_id = re.search(r"product/(\d+)", url)
        if reseller_id:
            return reseller_id.group(1)

    @staticmethod
    def _parse_price(response, product_json):
        currency = "USD"
        price = product_json.get('pricing', {}).get('promo_price')
        if not price:
            price = product_json.get('pricing', {}).get('price')
        if price:
            return Price(price=float(price), priceCurrency=currency)

    @staticmethod
    def _parse_image_url(response, product_json):
        image_url = product_json.get('img', {}).get('name')
        if image_url:
            image_url = 'https://s3-ap-southeast-1.amazonaws.com/media.redmart.com/newmedia/460x' + image_url
            return image_url

    @staticmethod
    def _parse_is_out_of_stock(response, product_json):
        if not product_json.get('inventory', {}).get('stock_status'):
            return True
        return False

    @staticmethod
    def _parse_was_now(response, product_json):
        if not product_json.get('pricing', {}).get('promo_price') == 0:
            now_price = product_json.get('pricing', {}).get('promo_price')
            old_price = product_json.get('pricing', {}).get('price')
            if now_price and old_price:
                return ', '.join([str(now_price), str(old_price)])

    @staticmethod
    def _parse_origin(response, product_json):
        contents = product_json.get('description_fields', {}).get('primary', [])
        for content in contents:
            if content.get('name') == "Country of Origin":
                return content.get('content')

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']

        buyer_review_values = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            review_json = json.loads(response.body)
            if review_json.get("BatchedResults", {}).get("q0", {}).get("Results", {}):
                review_statistics = review_json["BatchedResults"]["q0"]["Results"][0]['ReviewStatistics']

                if review_statistics.get("RatingDistribution", None):
                    for item in review_statistics['RatingDistribution']:
                        key = str(item['RatingValue'])
                        buyer_review_values["rating_by_star"][key] = item['Count']

                if review_statistics.get("TotalReviewCount", None):
                    buyer_review_values["num_of_reviews"] = review_statistics["TotalReviewCount"]

                if review_statistics.get("AverageOverallRating", None):
                    buyer_review_values["average_rating"] = format(review_statistics["AverageOverallRating"], '.1f')
        except Exception as e:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
        finally:
            buyer_reviews = BuyerReviews(**buyer_review_values)
            product['buyer_reviews'] = buyer_reviews
            return product

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            totals = data.get('total')
        except:
            self.log("Found no total matches {}".format(traceback.format_exc()))
            totals = 0

        return totals

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        try:
            data = json.loads(response.body_as_unicode())
            items = data.get('products', [])

            for item in items:
                res_item = SiteProductItem()
                res_item['url'] = 'https://m.redmart.com/product/' + item.get('details', {}).get('uri')
                link = self.PRODUCT_API_URL.format(item.get('details', {}).get('uri'))
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
            results_per_page = 18
        if (total_matches and results_per_page
            and current_page < math.ceil(total_matches / float(results_per_page))):
            current_page += 1
            response.meta['current_page'] = current_page
            return Request(self.SEARCH_URL.format(search_term=response.meta['search_term'],
                                                  page_num=current_page - 1),
                           meta=response.meta,
                           dont_filter=True)
