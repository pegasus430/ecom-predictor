# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import urlparse

from scrapy.log import INFO
from scrapy.conf import settings
from scrapy import Request
import traceback

from product_ranking.items import (SiteProductItem, Price, BuyerReviews)
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty
from product_ranking.guess_brand import guess_brand_from_first_words


class RcWilleyProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'rcwilley_products'
    allowed_domains = ["www.rcwilley.com", "rcwilley.com"]

    SEARCH_URL = "https://www.rcwilley.com/pg{page_num}/Search.jsp?q={search_term}"

    def __init__(self, *args, **kwargs):
        super(RcWilleyProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                page_num=1,
            ),
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)
        self.current_page = 1
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        #reseller ID
        reseller_id  = self._parse_reseller_id(response.url)
        cond_set_value(product, 'reseller_id', reseller_id)

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
        cond_set_value(product, 'description', description)

        # Parse stock status
        is_out_of_stock = self._parse_stock_status(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse buyer reviews
        buyer_reviews = self._parse_buyer_reviews(response)
        cond_set_value(product, 'buyer_reviews', buyer_reviews)

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//h1[@itemprop="name"]//text()').extract()
        if title:
            return "".join(title)

    def _parse_brand(self, response):
        brand = response.xpath('//span[@itemprop=brand]//text()').extract()
        if brand:
            return brand[0]
        return guess_brand_from_first_words(self._parse_title(response))

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath('//input[@name="sku"]/@value').extract()
        if sku:
            return sku[0]

    @staticmethod
    def _parse_reseller_id(url):
        reseller_id = re.search(r'\/(\d+?)\/', url)
        if reseller_id:
            return reseller_id.group(1)

    @staticmethod
    def _parse_categories(response):
        categories_sel = response.xpath('//ul[@id="breadCrumbs"]/li'
                                        '/a/span[@itemprop="title"]/text()').extract()
        categories = [i.strip() for i in categories_sel]
        return categories

    def _parse_price(self, response):
        currency = "USD"
        try:
            price = is_empty(response.xpath('//meta[@itemprop="price"]/@content').extract())
            if price:
                return Price(price=float(price.replace("$", '')), priceCurrency=currency)
        except:
            self.log("Error while parsing price : {}".format(traceback.format_exc()))

    @staticmethod
    def _parse_image_url(response):
        image_url = is_empty(response.xpath('//div[@id="prodImage"]/img[@id="mainImage"]/@src').extract())
        if image_url:
            image_url = urlparse.urljoin(response.url, image_url)
            return image_url

    @staticmethod
    def _parse_description(response):
        desc = is_empty(response.xpath('//div[@itemprop="description"]').extract())
        return desc

    @staticmethod
    def _parse_stock_status(response):
        out_of_stock = response.xpath('//meta[@itemprop="availability"]/@content').extract()

        if 'in_stock' in out_of_stock:
            return False

        return True

    def _parse_buyer_reviews(self, response):
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {}
        }
        try:
            rew_num = response.xpath('//div[@id="rating"]//span[@itemprop="count"]/text()').extract()
            if rew_num:
                rew_num = int(rew_num[0])

            average_rating = response.xpath('//div[@id="rating"]//meta[@itemprop="average"]/@content').extract()
            if average_rating:
                average_rating = str(average_rating[0])

            buyer_reviews = {
                'num_of_reviews': rew_num,
                'average_rating': round(float(average_rating), 1),
                'rating_by_star': {}
            }
            return buyer_reviews
        except:
            return BuyerReviews(**ZERO_REVIEWS_VALUE)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        totals = response.xpath('//div[contains(@class, "itemsSortedBy")]'
                                '/strong/text()').extract()
        try:
            if totals:
                return int(totals[0])
        except:
            self.log("Error while converting str to int {}".format(traceback.format_exc()))

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//div[@id="resultsContainer"]/a[@class="product"]/@href').extract()

        if items:
            for item in items:
                res_item = SiteProductItem()
                yield item, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        if self.current_page * response.meta['scraped_results_per_page'] >= response.meta['total_matches']:
            return

        self.current_page += 1
        return Request(url=self.SEARCH_URL.format(page_num=self.current_page,
                                                  search_term=response.meta['search_term']),
                       dont_filter=True, meta=response.meta)