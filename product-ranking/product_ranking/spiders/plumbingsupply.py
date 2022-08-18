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


class PlumbingSupplyProductsSpider(BaseValidator, BaseProductsSpider):

    name = 'plumbing_supply_products'
    allowed_domains = ["plumbingsupply.com"]

    SEARCH_URL = "https://www.plumbingsupply.com/cgi-bin/search.pl" \
                 "?a=s&thispage=&terms={search_term}"

    def __init__(self, *args, **kwargs):
        super(PlumbingSupplyProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        if '#' in product["url"]:
            title = re.search('#(.*)', product["url"]).group(1)
            url = '//h3[@id="{id}"]//text()'.format(id=title)
            title = is_empty(response.xpath(url).extract())
        else:
            title = is_empty(response.xpath('//head/title/text()').extract())
        cond_set_value(product, 'title', title, conv=string.strip)

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
    def _parse_categories(response):
        categories_sel = response.xpath('//div[contains(@class, "breadcrumbs")]'
                                        '//ul/li/a/text()').extract()
        categories = [i.strip() for i in categories_sel]
        return categories

    @staticmethod
    def _parse_price(response):
        currency = "USD"
        price = is_empty(response.xpath('//div[contains(@class, "price-info")]'
                                        '//span[@class="regular-price"]'
                                        '/span[@class="price"]/text()').extract())
        if price:
            return Price(price=float(price.replace("$", '')), priceCurrency=currency)

    @staticmethod
    def _parse_image_url(response):
        image_url = is_empty(response.xpath('//div[contains(@class, "leftfloat")]'
                                            '//img/@src').extract())
        if image_url:
            if 'https' in image_url:
                image_url = image_url
            else:
                image_url = urlparse.urljoin(response.url, image_url)
        else:
            image_url = is_empty(response.xpath('//p[contains(@class, "fs13")]'
                                                '//img/@src').extract())
            if image_url:
                image_url = urlparse.urljoin(response.url, image_url)
            else:
                image_url = ''

        return image_url

    @staticmethod
    def _parse_description(response):
        desc_list = ''
        description_list = response.xpath('//div[contains(@class, "leftfloat")]'
                                          '/ul/li//text()').extract()
        for description in description_list:
            desc_list += description

        return desc_list

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t]", "", text).strip()

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        totals = is_empty(response.xpath('//p[@class="fs18"]/text()').extract())
        if totals:
            total_count = re.search('\d+', totals)
            if total_count:
                return int(total_count.group(0))
            else:
                return 0
        else:
            return 0

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//ul[@class="ulnone"]'
                               '/li[@class="pb10"]/a/@href').extract()

        if items:
            for item in items:
                if not '#' in item:
                    item = urlparse.urljoin(response.url, item)
                    res_item = SiteProductItem()
                    yield item, res_item
                else:
                    self.log("Not a Product {url}".format(url=item), INFO)
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath('//p[@class="fs18"]/a[contains(@class, "searchbutton")]'
                                   '/@href').extract()
        if next_page:
            return urlparse.urljoin(response.url, next_page[0])