# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import urlparse

from scrapy.log import INFO
from scrapy.conf import settings

from product_ranking.items import (SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty


class AfoProductsSpider(BaseValidator, BaseProductsSpider):

    name = 'afo_products'
    allowed_domains = ["www.afo.com", "afo.com"]

    SEARCH_URL = "https://www.afo.com/catalogsearch/result/?q={search_term}"

    def __init__(self, *args, **kwargs):
        super(AfoProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

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

        return product

    @staticmethod
    def _parse_title(response):
        title = is_empty(response.xpath('//div[contains(@class, "product-shop")]'
                                        '/div[contains(@class, "product-name")]'
                                        '/span/text()').extract())
        return title

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
        categories_sel = response.xpath('//div[contains(@class, "breadcrumbs")]'
                                        '/ul/li/a/text()').extract()
        categories = [i.strip() for i in categories_sel]
        return categories

    @staticmethod
    def _parse_price(response):
        currency = "USD"
        price = is_empty(response.xpath('//*[@class="price"]/text()').extract())
        if price:
            return Price(price=float(price.replace("$", '')), priceCurrency=currency)

    @staticmethod
    def _parse_image_url(response):
        image_url = is_empty(response.xpath('//div[contains(@class, "product-image-gallery")]'
                                            '/img[@id="image-main"]/@src').extract())
        return image_url

    @staticmethod
    def _parse_description(response):
        desc = is_empty(response.xpath('//div[contains(@class, "short-description")]'
                                       '/div[contains(@class, "std")]/text()').extract())
        if desc:
            desc = desc.replace("<br>", "")

        return desc

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        totals = response.xpath('//div[@class="pager"]//p[contains(@class, "amount--has-pages")]'
                                '/text()').extract()
        if totals:
            totals = re.search('of\s(\d+)', totals[0])
            return int(totals.group(1)) if totals else 0

    def _scrape_results_per_page(self, response):
        item_count = is_empty(response.xpath('//div[contains(@class, "limiter")]'
                                             '/select/option[contains(@selected, "selected")]'
                                             '/text()').extract())
        if item_count:
            item_count = re.search('(\d+)', item_count)
            return item_count.group(1) if item_count else 0

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//ul[contains(@class, "products-grid")]'
                               '/li[contains(@class, "item")]'
                               '/a/@href').extract()

        if items:
            for item in items:
                res_item = SiteProductItem()
                yield item, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath('//div[@class="pages"]/ol/li'
                                   '/a[@title="Next"]/@href').extract()
        if next_page:
            return urlparse.urljoin(response.url, next_page[0])