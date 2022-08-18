from __future__ import absolute_import, division, unicode_literals

import json
import traceback
import urlparse
from scrapy.conf import settings
from datetime import datetime

import re
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import (BuyerReviews, Price, SiteProductItem)
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults
from product_ranking.utils import is_empty
from scrapy import Request


class LeviProductsSpider(BaseProductsSpider):
    name = 'levi_products'
    country = "US"
    locale = "en_US"
    allowed_domains = ["levi.com", "www.levi.com", "api.bazaarvoice.com"]
    start_urls = []

    SEARCH_URL = "https://www.levi.com/{country}/{locale}/search/{search_term}"  # TODO: ordering

    SWATCHES_URL = "https://www.levi.com/{country}/{locale}/p/{pid}/swatches"

    per_page = 72

    REVIEWS_URL = "https://api.bazaarvoice.com/data/batch.json?passkey=cahQRLJEuMvjxxJkeF12wrUy3WwLmgCQsS8BPlqmOOOA8&" \
                  "apiversion=5.5&displaycode=18056-en_us&resource.q0=products&filter.q0=id%3Aeq%3A{product_id}&stats.q0=" \
                  "reviews&filteredstats.q0=reviews&filter_reviews.q0=contentlocale%3Aeq%3Aen_US&filter_reviewcomments.q0=" \
                  "contentlocale%3Aeq%3Aen_US&resource.q1=reviews&filter.q1=isratingsonly%3Aeq%3Afalse&filter.q1=" \
                  "productid%3Aeq%3A181810040&filter.q1=contentlocale%3Aeq%3Aen_US&sort.q1=relevancy%3Aa1&stats.q1=" \
                  "reviews&filteredstats.q1=reviews&include.q1=authors%2Cproducts%2Ccomments&filter_reviews.q1=" \
                  "contentlocale%3Aeq%3Aen_US&filter_reviewcomments.q1=contentlocale%3Aeq%3Aen_US&filter_comments.q1=" \
                  "contentlocale%3Aeq%3Aen_US&limit.q1=8&offset.q1=0&limit_comments.q1=3&callback=BV._internal.dataHandler0"

    handle_httpstatus_list = [404]

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)

        super(LeviProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                country=self.country, locale=self.locale),
            site_name=self.allowed_domains[0], *args, **kwargs)

        self.user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) ' \
                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 ' \
                          'Safari/537.36 (Content Analytics)'

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2

        self.ignore_color_variants = kwargs.get('ignore_color_variants', True)
        if self.ignore_color_variants in ('0', False, 'false', 'False'):
            self.ignore_color_variants = False
        else:
            self.ignore_color_variants = True
        settings.overrides['USE_PROXIES'] = True

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _get_product_json(self, response):
        try:
            raw_data = re.search(
                r'LSCO.dtos = (.*?)LSCO.findFeatureValues',
                response.body,
                re.DOTALL | re.MULTILINE
            )
            return json.loads(raw_data.group(1))
        except:
            self.log("Failed to load main json: {}".format(traceback.format_exc()))

    def _get_json_from_response(self, response):
        try:
            data = re.search(r"<pdp-specs-component :product='(.+?)'", response.body, re.MULTILINE | re.DOTALL)
            return json.loads(data.group(1))
        except:
            self.log("Failed to load json from response: {}".format(traceback.format_exc()))
            return {}

    def parse_product(self, response):
        product = response.meta.get('product', SiteProductItem())

        if response.status == 404 or 'his product is no longer available' in response.body_as_unicode() \
                or "error" in response.url:
            product.update({"not_found": True})
            product.update({"no_longer_available": True})
            return product

        product_json = self._get_product_json(response)
        if not product_json:
            return product

        # brand
        cond_set_value(product, 'brand', 'Levi')

        # title
        cond_set_value(product, 'title', self._parse_title(response))

        # product_id, reseller_id, site_product_id
        product_id = self._parse_product_id(product['url'], product_json)
        cond_set_value(product, 'reseller_id', product_id)

        # oos
        cond_set_value(product, 'is_out_of_stock', self._parse_is_out_of_stock(response))

        # department, departments
        departments = self._parse_departments(response)
        if departments:
            cond_set_value(product, 'categories', departments)
            cond_set_value(product, 'department', departments[-1])

        # price_amount
        price_amount = self._parse_price_amount(product_json)
        price_currency = self._parse_price_currency(product_json)
        if price_amount and price_currency:
            cond_set_value(product, 'price', Price(price=price_amount, priceCurrency=price_currency))

        # image_url, image_urls, image_alts
        image_urls, image_alts = self._parse_images(response)
        if image_urls:
            cond_set_value(product, 'image_url', image_urls[0])

        # specs
        features = self._parse_features(response)
        cond_set_value(product, 'features', features)

        # variants
        variants_data = self._parse_variant_ids(product_json, price_amount)
        if variants_data:
            return Request(
                self.url_formatter.format(
                    self.SWATCHES_URL, pid=product_id),
                meta={
                    'item': product,
                    'variants_data': variants_data
                },
                dont_filter=True,
                callback=self._parse_swatches_status
            )
        else:
            # buyer_reviews
            return Request(
                url=self.REVIEWS_URL.format(product_id=product_id),
                meta={'item': product},
                callback=self._parse_buyer_reviews
            )

    def _parse_swatches_status(self, response):
        try:
            swatches = json.loads(response.body)
        except:
            self.log("Unable to parse swatches: {}".format(traceback.format_exc()))
            swatches = []
        finally:
            response.meta['swatches'] = swatches
            chosen_variant = is_empty(
                [x for x in response.meta['variants_data'] if x['id'] == response.meta['item']['reseller_id']])
            return Request(
                urlparse.urljoin(response.url, '/{}/{}{}'.format(self.country, self.locale,
                                                                 chosen_variant['url'] if chosen_variant else
                                                                 response.meta['variants_data'][0]['url'])),
                meta=response.meta,
                dont_filter=True,
                callback=self._parse_variants
            )

    @staticmethod
    def _parse_is_out_of_stock(response):
        return bool(response.xpath(
            '//button[contains(@class, "outOfStock")]'))

    @staticmethod
    def _parse_product_id(product_url, product_json):
        product_id = re.search(r'/p/(\d+)', product_url)
        return product_id.group(1) if product_id else product_json.get('code')

    @staticmethod
    def _parse_departments(response):
        departments = response.xpath(
            '//ol[@class="breadcrumb"]//li/a/text()'
        ).extract()
        return departments if departments else None

    @staticmethod
    def _parse_title(response):
        title = response.xpath(
            '//div[contains(@class, "-title")]/*[@itemprop="name"]/text()').extract()
        return is_empty(title)

    def _parse_price_amount(self, product_json):
        try:
            soft_price = product_json.get('product', {}).get('price', {}).get('softPrice')
            hard_price = product_json.get('product', {}).get('price', {}).get('hardPrice')
            regular_price = product_json.get('product', {}).get('price', {}).get('regularPrice')
            price_amount = soft_price or hard_price or regular_price
            return float(price_amount) if price_amount else None
        except:
            self.log("Found no price {}".format(traceback.format_exc()))

    def _parse_price_currency(self, product_json):
        try:
            return product_json.get('product', {}).get('price', {}).get('currencyIso')
        except:
            self.log("Found no price currency{}".format(traceback.format_exc()))
            return "USD"

    @staticmethod
    def _parse_images(response):
        urls = []
        alts = []
        images = response.xpath(
            '//picture//img'
        )
        for image in images:
            url = image.xpath('./@data-src').extract()
            if url and url[0].split('?'):
                urls.append(url[0].split('?')[0])
                alts.append(image.xpath('./@alt').extract()[0])
        return urls, alts

    @staticmethod
    def _parse_features(response):
        features = response.xpath(
            '//div[contains(@class, "pdp-spec-feature-list")]//li/text()'
        ).extract()
        return features if features else None

    @staticmethod
    def _parse_variant_ids(product_json, price_amount):
        return [{
            'colorName': x.get('colorName'),
            'id': x.get('code'),
            'url': x.get('url'),
            'active': x.get('active'),
            'price': price_amount
        } for x in product_json.get('swatches', [])]

    def _parse_variants(self, response):
        meta = response.meta
        product = response.meta.get('item')
        size_data = self._get_json_from_response(response)
        variants_data = meta.get('variants_data', [])
        swatches = meta.get('swatches', [])
        prod_json = self._get_product_json(response)
        variants = meta.get('variants', [])
        variant_data = is_empty([x for x in variants_data if x['id'] == size_data.get('code')])
        variants_data.pop(variants_data.index(variant_data))
        if variant_data:
            for data in size_data.get('variantOptions', []):
                var = {
                    'colorid': variant_data.get('id'),
                    'price': self._parse_price_amount(prod_json),
                    'properties': {
                        'color': variant_data.get('colorName'),
                        'size': data.get('displaySizeDescription')
                    },
                    'selected': variant_data.get('active'),
                    'url': urlparse.urljoin(response.url, '/{}/{}{}'.format(self.country, self.locale,
                                                                            variant_data['url'])),
                }
                swatch = is_empty([swatch for swatch in swatches if swatch.get('code') == var['colorid']])
                if swatch:
                    statuses = swatch.get('variantsAvailability', [])
                    status = is_empty(
                        [status for status in statuses if status.get("size") == var['properties']['size']])
                    if status:
                        var['in_stock'] = status.get('available')
                variants.append(var)

            cond_set_value(product, 'variants', variants)

            if not self.ignore_color_variants and variants_data:
                meta['variants'] = variants
                return Request(
                    url=urlparse.urljoin(response.url, '/{}/{}{}'.format(self.country, self.locale,
                                                                         variants_data[0]['url'])),
                    dont_filter=True,
                    meta=response.meta,
                    callback=self._parse_variants
                )
        return Request(
            url=self.REVIEWS_URL.format(product_id=product.get('reseller_id')),
            meta={'item': product},
            callback=self._parse_buyer_reviews
        )

    @staticmethod
    def _clean_reviews(response):
        data = re.search(r'BV._internal.dataHandler0\((.+)\)', response.body_as_unicode())
        return data.group(1) if data else None

    def _parse_buyer_reviews(self, response):
        product = response.meta.get('item')
        buyer_reviews = BuyerReviews(*self.br.ZERO_REVIEWS_VALUE)
        try:
            reviews = json.loads(self._clean_reviews(response))
            reviews = reviews.get('BatchedResults', {}).get('q0', {}).get('Results')
            if reviews and isinstance(reviews, list):
                reviews = reviews[0].get('ReviewStatistics', {})

            if reviews:
                last_review = reviews.get('LastSubmissionTime')
                if last_review:
                    product['last_buyer_review_date'] = datetime.strptime(
                        last_review.split('.')[0],
                        '%Y-%m-%dT%H:%M:%S'
                    )
                if reviews:
                    average = reviews.get('AverageOverallRating', 0)
                    stars = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                    for star in reviews.get('RatingDistribution', []):
                        stars[star.get('RatingValue')] = star.get('Count', 0)
                    buyer_reviews = BuyerReviews(
                        rating_by_star=stars,
                        num_of_reviews=reviews.get('TotalReviewCount', 0),
                        average_rating=average if average else 0
                    )
        except:
            self.log("Failed to parse reviews: {}".format(traceback.format_exc()))

        cond_set_value(product, 'buyer_reviews', buyer_reviews)
        return product

    def parse_locale(self):
        return self.locale

    def _scrape_total_matches(self, response):
        total_matches = response.xpath(
            '//div[@class="pagination-bar-results"]/text()'
        ).re(r'\d+,*\d*')
        return int(total_matches[0].replace(',', '')) if total_matches else None

    def _scrape_product_links(self, response):
        links = response.xpath('//a[@class="name"]/@href').extract()
        for link in links:
            yield urlparse.urljoin(response.url, link), SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next = response.xpath('//a[@rel="next"]/@href').extract()
        if next:
            return Request(urlparse.urljoin(response.url, next[0]),
                           meta=response.meta
                           )

    def _get_products(self, response):
        for req in super(LeviProductsSpider, self)._get_products(response):
            req = req.replace(dont_filter=True)
            yield req
