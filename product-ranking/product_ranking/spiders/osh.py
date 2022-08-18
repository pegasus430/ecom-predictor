# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import traceback
import urlparse

from scrapy.conf import settings
from scrapy.log import INFO

from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty
from product_ranking.validation import BaseValidator


class OshProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'osh_products'
    allowed_domains = ["www.osh.com", "osh.com"]

    SEARCH_URL = "http://www.osh.com/search?text={search_term}&search=Search"

    def __init__(self, *args, **kwargs):
        super(OshProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        self.current_page = 0

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku, conv=string.strip)

        # Parse reseller_id
        product['reseller_id'] = sku

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

        # Parse is_in_store_only
        product['is_in_store_only'] = self._parse_is_in_store_only(response)

        # Parse is_out_of_stock
        product['is_out_of_stock'] = self._parse_is_out_of_stock(response)

        return product

    @staticmethod
    def _parse_title(response):
        title = is_empty(response.xpath('//div[@class="osh-sticky-price"]/h1/text()').extract())
        return title

    @staticmethod
    def _parse_sku(response):
        sku = is_empty(response.xpath('//h4[contains(text(), "Sku")]/following-sibling::p/text()').extract())
        return sku

    @staticmethod
    def _parse_categories(response):
        categories_sel = response.xpath('//div[contains(@class, "breadcrumb")]'
                                        '/span/a/text()').extract()
        categories = [i.strip() for i in categories_sel]
        return categories

    def _parse_price(self, response):
        currency = "USD"
        try:
            price = is_empty(response.xpath('//*[@class="product_saleprice"]/span/text()').extract())
            if price:
                return Price(price=float(price.replace("$", '')), priceCurrency=currency)
        except:
            self.log("Error while parsing price : {}".format(traceback.format_exc()))

    @staticmethod
    def _parse_image_url(response):
        image_url = is_empty(response.xpath('//div[contains(@class, "swiper-slide")]/img/@src').extract())
        if image_url:
            return urlparse.urljoin(response.url, image_url)

    @staticmethod
    def _parse_is_in_store_only(response):
        return bool(response.xpath('//span[@class="stock-info-avaiable"]/span[contains(., "In Store Only")]'))

    @staticmethod
    def _parse_is_out_of_stock(response):
        return bool(response.xpath('//button[@class="addtocart btn-primary-green disabled"]'))

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        totals = response.xpath('//div[@id="osh-count-summary-mobile-0"]/span/text()').re(r'(\d+)')
        if totals:
            return int(totals[-1])

    def _scrape_results_per_page(self, response):
        item_count = response.xpath('//li[@class="countsummary"]/span/text()').extract()
        if item_count:
            item_count = re.search(r'1-(\d+) of', item_count[0])
            return int(item_count.group(1)) if item_count else 0

    def _scrape_product_links(self, response):
        items = response.xpath('//div[@class="osh-product-thumb"]/a/@href').extract()

        if items:
            for item in items:
                res_item = SiteProductItem()
                link = urlparse.urljoin(response.url, item)
                yield link, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        if 24 * (self.current_page) < int(response.meta.get('total_matches', 0)):
            self.current_page += 1
            return urlparse.urljoin(
                response.url, '/search?q={search_term}&page={page}&lazyload=true'.format(
                    search_term=response.meta.get('search_term'),
                    page=self.current_page
                )
            )
