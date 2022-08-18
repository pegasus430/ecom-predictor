# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import urlparse
import traceback

from scrapy.log import INFO
from scrapy.conf import settings

from product_ranking.items import (SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty


class StoreGoogleProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'store_google_products'
    allowed_domains = ["store.google.com"]

    SEARCH_URL = "https://store.google.com/search?q={search_term}"

    def __init__(self, *args, **kwargs):
        super(StoreGoogleProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
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

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//div[contains(@class, "title-price-container")]'
                               '/h1[@itemprop="name"]/text()').extract()
        if title:
            return title[0]

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//meta[@itemprop="brand"]/@content').extract()
        if brand:
            return brand[0]

    def _parse_price(self, response):
        currency = "USD"
        try:
            price = is_empty(response.xpath('//div[@class="description-text"]'
                                            '//span[@class="is-price"]/text()').extract())
            price = re.search('\d+\.?\d+', price).group()
            return Price(price=float(price), priceCurrency=currency)
        except:
            self.log("Error while parsing price {}".format(traceback.format_exc()))

    @staticmethod
    def _parse_image_url(response):
        image_url = None
        base_image_url = response.xpath('//ul[contains(@class, "pagination-list")]'
                                        '/li//div/@data-default-src').extract()
        special_img_url = response.xpath('//div[contains(@class, "background")]'
                                         '/@data-default-src').extract()
        if base_image_url:
            image_url = base_image_url[0]
        elif special_img_url:
            image_url = 'https:' + special_img_url[0]

        return image_url

    @staticmethod
    def _parse_description(response):
        desc = response.xpath('//meta[@name="description"]/@content').extract()
        if desc:
            return desc[0]

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        totals = response.xpath('//div[@class="search-results-header"]/text()').extract()
        if totals:
            totals = re.search('(\d+)', totals[0])
            return int(totals.group(1)) if totals else 0

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//div[contains(@class, "search-results-grid")]'
                               '//a[@class="card-link-target"]/@href').extract()

        if items:
            for item in items:
                res_item = SiteProductItem()
                link = urlparse.urljoin(response.url, item)
                yield link, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath('//div[@class="pages"]/ol/li'
                                   '/a[@title="Next"]/@href').extract()
        if next_page:
            return urlparse.urljoin(response.url, next_page[0])