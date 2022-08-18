# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import urlparse

import traceback
import json

from scrapy import Request
from HTMLParser import HTMLParser
from scrapy.log import INFO, WARNING
from scrapy.conf import settings

from product_ranking.items import (BuyerReviews, SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty

class MichaelsProductsSpider(BaseValidator, BaseProductsSpider):

    name = 'michaels_products'
    allowed_domains = ["www.michaels.com", "michaels.com"]

    SEARCH_URL = "http://www.michaels.com/search?q={search_term}"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
                 "passkey=artgqo0gyla0epe3aypxybrs5&apiversion=5.5&" \
                 "displaycode=9022-en_us&" \
                 "resource.q0=products&" \
                 "filter.q0=id:eq:{prod_id}&" \
                 "stats.q0=reviews&"

    HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/57.0.2987.110 Safari/537.36"}

    def __init__(self, *args, **kwargs):
        super(MichaelsProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        out_of_stock = self._parse_out_of_stock(response)
        product['is_out_of_stock'] = out_of_stock

        # Parse model
        model = self._parse_model(response)
        cond_set_value(product, 'model', model, conv=string.strip)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        # Product Id
        product_id = re.findall('configData.productId = (.*?);', response.body)

        # Parse buyer reviews
        reqs = []
        if product_id:
            product_id = product_id[0].replace('"', '')
            reqs.append(Request(self.REVIEW_URL.format(prod_id=product_id),
                                dont_filter=True,
                                meta=response.meta,
                                callback=self._parse_buyer_reviews,
                                headers=self.HEADERS))
            return reqs

        return product

    @staticmethod
    def _parse_title(response):
        title = is_empty(response.xpath('//div[contains(@class, "product-header")]'
                                        '/h1[contains(@class, "product-name")]'
                                        '/text()').extract())
        return HTMLParser().unescape(title) if title else None

    @staticmethod
    def _parse_model(response):
        model = is_empty(response.xpath('//div[contains(@class, "short-description")]'
                                        '/span[@class="h4"]/text()').extract())
        r = re.compile('(\d+)')

        if model:
            model = filter(r.match, model)
            return model

    @staticmethod
    def _parse_categories(response):
        categories_sel = response.xpath('//ol[@class="breadcrumb"]'
                                        '/li/a/text()').extract()
        categories = [i.strip() for i in categories_sel]
        return categories

    def _parse_price(self, response):
        currency = "USD"

        try:
            if re.search('From:', response.body):
                price = re.search('From:</span>(.*?)</div>', response.body, re.DOTALL).group(1).strip()
            else:
                price = is_empty(response.xpath('//div[contains(@class, "product-pricing")]'
                                                '/div[contains(@class, "product-sales-price")]/text()').extract()).strip()

            price = price.replace('$', '')
            return Price(price=float(price.replace(',', '')), priceCurrency=currency)
        except:
            self.log('Error while parsing price'.format(traceback.format_exc()), WARNING)
            return None

    @staticmethod
    def _parse_image_url(response):
        image_url = is_empty(response.xpath('//div[contains(@class, "product-image-container")]'
                                            '/div/img/@src').extract())
        return image_url

    @staticmethod
    def _parse_description(response):
        description = ''
        description_elements = response.xpath('//div[contains(@class, "productshortDescriptions")]'
                                              '//text()').extract()
        for desc in description_elements:
            description += desc

        return description

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']
        zero_reviews_value = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            data = json.loads(response.body_as_unicode())

            results = data.get("BatchedResults", {}).get("q0", {}).get("Results")[0]

            if "Name" in results.get("Brand"):
                product['brand'] = results.get("Brand").get("Name")

            data = results.get("ReviewStatistics")
            review_count = data.get('TotalReviewCount')

            rating_by_star = {}
            stars = data.get("RatingDistribution", [])
            for star in stars:
                rating_by_star[star['RatingValue']] = star['Count']

            average_rating = data.get("AverageOverallRating", 0)

            buyer_reviews = {
                'num_of_reviews': review_count,
                'average_rating': round(float(average_rating), 1) if average_rating else 0,
                'rating_by_star': rating_by_star
            }
            product['buyer_reviews'] = buyer_reviews

        except Exception as e:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()), WARNING)
            return BuyerReviews(**zero_reviews_value)

        return product

    @staticmethod
    def _parse_out_of_stock(response):
        availability = is_empty(response.xpath('//meta[@property="og:availability"]/@content').extract())

        return not bool(availability == "instock")

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        totals = response.xpath('//div[@class="page-range"]'
                                '/span[@class="result-count"]/text()').extract()
        return int(totals[0].replace(',', '')) if totals else 0

    def _scrape_results_per_page(self, response):
        item_count = is_empty(response.xpath('//div[contains(@class, "custom-select")]'
                                             '/select[@id="grid-paging-header"]'
                                             '/option[contains(@selected, "selected")]'
                                             '/text()').extract())
        return item_count

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//div[@class="product-image"]'
                               '/a[@class="thumb-link"]/@href').extract()

        if items:
            for item in items:
                res_item = SiteProductItem()
                yield item, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath('//a[@class="page-next"]/@href').extract()
        if next_page:
            return urlparse.urljoin(response.url, next_page[0])