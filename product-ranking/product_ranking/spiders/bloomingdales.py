# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals
import json
import traceback
import re
from lxml import html
from urlparse import urljoin

from scrapy.http import Request
from scrapy.log import WARNING
from scrapy.conf import settings
from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, FLOATING_POINT_RGEX, cond_set_value
from spiders_shared_code.bloomingdales_variants import BloomingDalesVariants


class BloomingDalesProductsSpider(BaseProductsSpider):
    name = 'bloomingdales_products'
    allowed_domains = ["bloomingdales.com", "bloomingdales.ugc.bazaarvoice.com"]

    REVIEW_URL = 'https://bloomingdales.ugc.bazaarvoice.com/7130aa/{product_id}/reviews.djs?format=embeddedhtml'
    SEARCH_URL = 'https://www.bloomingdales.com/shop/search?keyword={search_term}'

    cookies = {

        "SignedIn": "0",
        "currency": "USD",
        "mercury": True,
        "shippingCountry": "US"
    }

    def __init__(self, *args, **kwargs):
        settings.overrides['USE_PROXIES'] = True
        self.bv = BloomingDalesVariants()
        super(BloomingDalesProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US;q=0.8,en;q=0.7,es;q=0.6,de;q=0.5',
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36'
        }

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def start_requests(self):
        headers = self.headers.copy()
        for request in super(BloomingDalesProductsSpider, self).start_requests():
            request = request.replace(headers=headers, dont_filter=True,
                                      cookies=self.cookies
                                     )
            yield request

    def parse_product(self, response):
        product = response.meta['product']

        product['locale'] = 'en-US'
        product_json = self._parse_product_json(response)

        if not product_json:
            cond_set_value(product, 'no_longer_available', True)
            return product

        title = self._parse_title(product_json)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(product_json)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(product_json)
        cond_set_value(product, 'image_url', image_url)

        desc = self._parse_description(product_json)
        cond_set_value(product, 'description', desc)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        department = categories[-1] if categories else None
        cond_set_value(product, 'department', department)

        price = self._parse_price(product_json, response)
        cond_set_value(product, 'price', price)

        was_now = self._parse_was_now(product_json)
        cond_set_value(product, 'was_now', was_now)

        save_percent = self._parse_save_percent(product_json)
        cond_set_value(product, 'save_percent', save_percent)

        promotions = True if was_now else False
        cond_set_value(product, 'promotions', promotions)

        num_of_reviews = product_json.get('numberOfReviews')
        product_id = product_json.get('productId')

        variants = self._parse_variants()
        cond_set_value(product, 'variants', variants)

        reseller_id = self._parse_reseller_id(product.get('url', ''))
        cond_set_value(product, 'reseller_id', reseller_id)

        if num_of_reviews and product_id:
            averating_reviews = product_json.get('custRating')
            url = self.REVIEW_URL.format(product_id=product_id)
            return Request(
                url=url,
                callback=self._parse_buyer_reviews,
                meta={
                    'product': product,
                    'averating_reviews': averating_reviews,
                    'num_of_reviews': num_of_reviews
                },
                dont_filter=True
            )

        return product

    def _parse_product_json(self, response):
        try:
            product_json = re.search(r'var pdp = (.*?);\n', response.body_as_unicode(),
                                     re.MULTILINE | re.DOTALL)
            product_json = product_json.group(1)
            product_json = json.loads(product_json)
            product_json = product_json.get('product')
            self.bv.setupSC(product_json)
            return product_json
        except:
            self.log('Parsing Error of Product Json: {}'.format(traceback.format_exc()))

    @staticmethod
    def _parse_title(product_json):
        return product_json.get('pdfEmailDescription')

    @staticmethod
    def _parse_brand(product_json):
        return product_json.get('brand')

    @staticmethod
    def _parse_image_url(product_json):
        return 'https://images.bloomingdales.com/is/image/BLM/products/' + product_json.get('imageSource') \
            if product_json.get('imageSource') \
            else None

    @staticmethod
    def _parse_description(product_json):
        return product_json.get('longDescription')

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//div[contains(@class, "breadCrumbs")]//a[not(text()="Home")]/text()').extract()
        return categories if categories else None

    @staticmethod
    def _parse_price(product_json, response):
        price = product_json.get('colorwayPrice', {}).get('retailPrice')
        price_currency = response.xpath('//meta[@itemprop="priceCurrency"]/@content').extract()
        price_currency = price_currency[0] if price_currency else 'USD'
        return Price(price=price, priceCurrency=price_currency) if price else None

    @staticmethod
    def _parse_was_now(product_json):
        old_price = product_json.get('price', [])
        new_price = product_json.get('salePrice', [])
        return str(new_price[0]) + ', ' + str(old_price[0]) if old_price and new_price else None

    @staticmethod
    def _parse_save_percent(product_json):
        return product_json.get('colorwayPrice').get('percentageOff')

    def _parse_variants(self):
        return self.bv._variants()

    @staticmethod
    def _parse_reseller_id(url):
        reseller_id = re.search('ID=(\d+)', url, re.DOTALL)
        return reseller_id.group(1) if reseller_id else None

    def _parse_buyer_reviews(self, response):
        meta = response.meta.copy()
        product = meta.get('product')
        average_rating = meta.get('average_rating')
        num_of_reviews = meta.get('num_of_reviews')
        buyer_review_values = {
            'num_of_reviews': num_of_reviews,
            'average_rating': average_rating,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        data = re.search('BVRRRatingSummarySourceID":"(.+?)\},', response.body_as_unicode())
        try:
            data = data.group(1).replace('\\"', '"').replace("\\/", "/")
            review_html = html.fromstring(data)

            review_list = review_html.xpath('//div[@class="BVRRHistogramContent"]'
                                            '/div[contains(@class, "BVRRHistogramBarRow")]'
                                            '/span[@class="BVRRHistAbsLabel"]/text()')

            for i in range(5):
                buyer_review_values['rating_by_star'][str(5 - i)] = int(review_list[i].replace(',', ''))
            buyer_review_values = BuyerReviews(**buyer_review_values)
            cond_set_value(product, 'buyer_reviews', buyer_review_values)
        except:
            self.log('Error Parsing Reviews: {}'.format(traceback.format_exc()))
        return product

    def _scrape_total_matches(self, response):
        total_matches = re.search('"productCount":(\d+),', response.body)
        return int(total_matches.group(1)) if total_matches else 0

    def _scrape_product_links(self, response):
        links = response.xpath('//div[@class="productThumbnailImage"]/a[@class="productDescLink"]/@href').extract()
        for link in links:
            link = urljoin(response.url, link)
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        pagination = response.xpath('//script[@data-bootstrap="feature/canvas"]/text()').extract()
        if pagination:
            try:
                pagination = json.loads(pagination[0])
                next_url = pagination.get('model', {}).get('pagination', {}).get('nextURL')
                return Request(
                    url=urljoin(response.url, next_url),
                    meta=response.meta,
                    headers=self.headers,
                    dont_filter=True
                ) if next_url else None
            except:
                self.log('Error Parsing Pagination Json: {}'.format(traceback.format_exc()), WARNING)

    def _get_products(self, response):
        for request in super(BloomingDalesProductsSpider, self)._get_products(response):
            yield request.replace(dont_filter=True, cookies=self.cookies)
