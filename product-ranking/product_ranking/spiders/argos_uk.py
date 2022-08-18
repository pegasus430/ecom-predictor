# -*- coding: utf-8 -*-

import re
import urlparse
import json
import traceback

from scrapy import Request
from scrapy.log import ERROR, WARNING

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty


class ArgosUKProductsSpider(BaseProductsSpider):
    name = 'argos_uk_products'
    allowed_domains = ["argos.co.uk"]

    SEARCH_URL = 'http://www.argos.co.uk/search/{search_term}/'
    PRODUCT_URL = 'http://www.argos.co.uk/product/{product_id}'

    SORT_MODES = {
        "price_asc": "price",
        "price_desc": "price:desc",
        "rating": "customer-rating",
    }

    def __init__(self, sort_mode=None, *args, **kwargs):
        if sort_mode and sort_mode in self.SORT_MODES:
            sort_mode = self.SORT_MODES[sort_mode]
            self.SEARCH_URL += 'opt/sort:{}/'.format(sort_mode)
        super(ArgosUKProductsSpider, self).__init__(*args, **kwargs)

    def _parse_single_product(self, response):
      return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        try:
            json_data = re.search('window.App=(.*})<', response.body)
            js = json.loads(json_data.group(1))
        except ValueError:
            self.log('JSON not found: {}'.format(traceback.format_exc()), ERROR)
            product['not_found'] = True
            return product

        product_info = js.get('context', {}).get('dispatcher', {}).get('stores', {}) \
            .get('ProductStore', {})

        data = product_info.get('attributes', {})

        not_found = product_info.get('not_found', False)
        if not_found:
            product['not_found'] = True
            return product

        title = data.get('name')
        cond_set_value(product, 'title', title)

        description = data.get('description')
        cond_set_value(product, 'description', description)

        if description:
            has_ean = re.search('EAN: (\d+)', description)
            if has_ean:
                cond_set_value(product, 'upc', has_ean.group(1))

        price = data.get('price', {})
        if price:
            cond_set_value(product, 'price', Price(
                price=price.get('now', 0), priceCurrency='GBP'))
            special_pricing = bool(price.get('was'))
            cond_set_value(product, 'special_pricing', special_pricing)

        brand = data.get('brand')
        if not brand:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        images = product_info.get('media', {}).get('images')
        if images:
            cond_set_value(product, 'image_url', images[0])

        is_out_of_stock = data.get('globallyOutOfStock')
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        sku = data.get('partNumber')
        cond_set_value(product, 'sku', sku, conv=unicode)

        breadcrumb = product_info.get('breadcrumb', [])
        cats = [cat.get('attributes', {}).get('name') for cat in breadcrumb]
        if any(cats):
            cond_set_value(product, 'categories', cats)
            cond_set_value(product, 'department', cats[-1])

        cond_set_value(product, 'locale', 'en-GB')

        buyer_reviews = self._parse_buyer_reviews(js)
        cond_set_value(product, 'buyer_reviews', buyer_reviews)

        variants = self._parse_variants(product_info)
        cond_set_value(product, 'variants', variants)

        return product

    def _parse_variants(self, product_info):
        variants = []
        items = product_info.get('variants', {}).get('attributes', {}) \
            .get('variants', [])
        for item in items:
            properties = {}
            for attr in item.get('attributes', []):
                key = attr.get('type')
                value = attr.get('value')
                if key and value:
                    properties[key] = value
            variant = {
                'properties': properties,
                'price': item.get('price'),
                'sku': item.get('partNumber'),
            }
            variants.append(variant)

        return variants

    def _parse_buyer_reviews(self, js):
        reviews = js.get('context', {}).get('dispatcher', {}) \
            .get('stores', {}).get('BazaarVoiceReviewStore', {}).get('stats') \
            .get('attributes', {})
        rating_by_stars = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        for dist in reviews.get('ratingDistribution', []):
            rating_by_stars[str(dist['RatingValue'])] = dist['Count']

        buyer_reviews = {
            'num_of_reviews': reviews.get('reviewCount', 0),
            'average_rating': round(reviews.get('overallRating', 0), 1),
            'rating_by_star': rating_by_stars
        }
        return BuyerReviews(**buyer_reviews)

    def _scrape_total_matches(self, response):
        if '/static/' in response.url:
            total = is_empty(
                response.xpath(
                    '//div[@id="categorylist"]/h2/span/text()'
                ).re('(\d+)'), '0'
            )
            return int(total)

        json_data = re.search('window.App=(.*})<', response.body)
        if not json_data:
            self.log('JSON not found', WARNING)
            return 0
        try:
            js = json.loads(json_data.group(1))
        except ValueError:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
            return 0

        total = js.get('context', {}).get('dispatcher', {}).get('stores', {}) \
                .get('ProductStore', {}).get('numberOfResults', 0)

        return total

    def _scrape_next_results_page_link(self, response):
        next_page = is_empty(
            response.xpath(
                '//li[@class="pagination-next"]/a/@href |'
                '//a[@rel="next"]/@href'
            ).extract()
        )

        if next_page:
            return urlparse.urljoin(response.url, next_page)

    def _scrape_product_links(self, response):
        if '/static/' in response.url:
            pids = response.xpath(
                '//dl[contains(@class, "product")]/@name'
            ).extract()
        else:
            json_data = re.search('window.App=(.*})<', response.body)
            if not json_data:
                self.log('JSON not found', WARNING)
                return
            try:
                js = json.loads(json_data.group(1))
            except ValueError:
                self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
                return

            products = js.get('context', {}).get('dispatcher', {}) \
                .get('stores', {}).get('ProductStore', {}).get('products', [])
            pids = [product.get('id') for product in products]

        for product_id in pids:
            if product_id:
                url = self.PRODUCT_URL.format(product_id=product_id)
                yield url, SiteProductItem()
