# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import json
import re
import string
import traceback
import urlparse
from HTMLParser import HTMLParser

from scrapy import Request
from scrapy.conf import settings
from scrapy.log import INFO, WARNING

from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty
from product_ranking.validation import BaseValidator


class HomedepotcaProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'homedepotca_products'
    allowed_domains = ["www.homedepot.ca", "homedepot.ca"]

    SEARCH_URL = "https://www.homedepot.ca/en/home/search.html?q={search_term}"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
                 "passkey=i2qqfxgqsb1f86aabybalrdvf&apiversion=5.5&" \
                 "displaycode=1998-en_ca&" \
                 "resource.q0=products&" \
                 "filter.q0=id:eq:{prod_id}&" \
                 "stats.q0=reviews&"

    PRICE_URL = "https://www.homedepot.ca/homedepotcacommercewebservices/v2/homedepotca" \
                "/products/{sku}/localized/7073?catalogVersion=Online&lang=en"

    IMAGE_URL = "https://images.homedepot.ca/is/image/homedepotcanada/p_{sku}.jpg"

    def __init__(self, *args, **kwargs):
        super(HomedepotcaProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        self.user_agent = 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'
        settings.overrides['USE_PROXIES'] = True
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares
        settings.overrides['DOWNLOAD_DELAY'] = 1
        settings.overrides['CONCURRENT_REQUESTS'] = 2
        settings.overrides['COOKIES_ENABLED'] = False
        settings.overrides['REFERER_ENABLED'] = False

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_CA'

        # Parse title
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        out_of_stock = self._parse_out_of_stock(response)
        product['is_out_of_stock'] = out_of_stock

        # Parse model
        model = self._parse_model(response)
        cond_set_value(product, 'model', model, conv=string.strip)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku, conv=string.strip)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse image
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        available_online = self._parse_available_online(response)
        cond_set_value(product, 'available_online', available_online)

        is_in_store_only = self._parse_is_in_store_only(response)
        cond_set_value(product, 'is_in_store_only', is_in_store_only)

        # Product Id
        product_id = is_empty(response.xpath('//div[contains(@class, "product-accordion-content")]'
                                             '/div/@data-product-id').extract())

        # Parse buyer reviews
        if product_id:
            cond_set_value(product, 'reseller_id', product_id)
            return Request(self.REVIEW_URL.format(prod_id=product_id), dont_filter=True,
                           meta=response.meta, callback=self._parse_buyer_reviews)
        return product

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//h3[@class="pip-product-brand"]/span/text()').extract()
        if brand:
            return HTMLParser().unescape(brand[0])

    @staticmethod
    def _parse_title(response):
        title = is_empty(response.xpath('//h1[@itemprop="name"]/text()').extract())
        return HTMLParser().unescape(title) if title else None

    @staticmethod
    def _parse_model(response):
        model = response.xpath('//div[@class="product-models"]/text()').extract()
        model = re.search('(.*)Store', model[0], re.DOTALL)
        if model:
            model = model.group(1)
            model = re.search('# (.*)', model)
            return model.group(1) if model else None

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath('//div[@class="product-models"]'
                             '/text()').extract()
        if sku:
            sku = re.search('SKU(.*)', sku[0], re.DOTALL)
            r = re.compile('(\d+)')
            model = filter(r.match, sku.group(1))
            return model[:10]

    @staticmethod
    def _parse_categories(response):
        categories_sel = response.xpath('//ol[@class="breadcrumb"]'
                                        '/li/a/text()').extract()
        categories = [i.strip() for i in categories_sel]
        return categories

    def _parse_price(self, response):
        product = response.meta["product"]
        product["price"] = None
        try:
            data = json.loads(response.body)
            if data["optimizedPrice"].get("displayPrice", None):
                price = data["optimizedPrice"]["displayPrice"]["value"]
                currency = data["optimizedPrice"]["displayPrice"]['currencyIso']
                product["price"] = Price(price=price, priceCurrency=currency)
        except:
            self.log("Error while parsing price: {}".format(traceback.format_exc()), WARNING)

        return product

    def _parse_image_url(self, response):
        sku = self._parse_sku(response)
        if sku:
            image_url = self.IMAGE_URL.format(sku=sku)
            return image_url

    @staticmethod
    def _parse_available_online(response):
        available_online = response.xpath('//input[@id="shipOptionHome"]'
                                          '| //input[@name="postalCode"]').extract()
        return bool(available_online)

    def _parse_is_in_store_only(self, response):
        is_in_store_only = response.xpath('//input[@id="shipOptionPickup" and @checked]')
        return bool(is_in_store_only) and not self._parse_available_online(response)

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

        except:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()), WARNING)
            product['buyer_reviews'] = BuyerReviews(**zero_reviews_value)

        # Parse price
        sku = product["sku"]
        if sku:
            response.meta['handle_httpstatus_list'] = [400]
            return Request(url=self.PRICE_URL.format(sku=sku),
                           meta=response.meta,
                           dont_filter=True,
                           callback=self._parse_price)

        return product

    @staticmethod
    def _parse_out_of_stock(response):
        availability = is_empty(response.xpath('//div[contains(@class, "stock-status")]/text()').extract())

        return availability == "In Stock"

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        totals = response.xpath('//div[contains(@class, "products-search-results")]'
                                '/div/@data-total-number-of-results').extract()
        return int(totals[0]) if totals else 0

    def _scrape_results_per_page(self, response):
        item_count = response.xpath('//button[@name="items-per-page_btn"]/span/text()').re('\d+')
        if item_count:
            item_count = int(item_count[0])
            return item_count

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//div[contains(@class, "searcher-product-container")]'
                               '//a[@class="hdca-product-box__header-intro"]/@href').extract()

        if items:
            for item in items:
                link = urlparse.urljoin(response.url, item)
                res_item = SiteProductItem()
                yield link, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath('//li[@class="next hidden-mobile"]'
                                   '/a[@aria-label="Next page"]/@href').extract()
        if next_page:
            return Request(
                urlparse.urljoin(response.url, next_page[0]),
                meta=response.meta,
            )
