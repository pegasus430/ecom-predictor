# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import urlparse
import traceback
import math

from scrapy.log import INFO
from scrapy.conf import settings
from scrapy import Request

from product_ranking.items import (SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty


class LoblawscaProductsSpider(BaseValidator, BaseProductsSpider):

    name = 'loblawsca_products'
    allowed_domains = ["loblaws.ca"]

    SEARCH_URL = "https://www.loblaws.ca/search/?search-bar={search_term}"

    NEXT_URL = "https://www.loblaws.ca/search/showMoreProducts/~item/{search_term}/~sort/" \
               "recommended/~selected/true?itemsLoadedonPage={page_num}"

    COOKIE = {
        'JSESSIONID': '63D2C23EB00D07A3DB78E530D8844060.app4prjvm0;',
        'AMCV_99911CFE5329657B0A490D45%40AdobeOrg': '1099438348'
                                                    '%7CMCIDTS%7C17455%7CMCMID'
                                                    '%7C05039285206316450512638603321864119069%7CMCAAMLH-1508417991'
                                                    '%7C9%7CMCAAMB-1508736008%7CNRX38WO0n5BH8Th-nqAG_A'
                                                    '%7CMCOPTOUT-1508138408s%7CNONE%7CMCAID'
                                                    '%7C2CEFB3A485035A0C-4000119EE0000290%7CMCSYNCSOP'
                                                    '%7C411-17459%7CvVersion%7C2.1.0;'
    }

    def __init__(self, *args, **kwargs):
        super(LoblawscaProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        for request in super(LoblawscaProductsSpider, self).start_requests():
            request = request.replace(cookies=self.COOKIE)
        yield request

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_CA'

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse model
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku, conv=string.strip)

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
    def _parse_brand(response):
        brand = is_empty(response.xpath('//span[@class="product-sub-title"]/text()').extract())
        return brand.strip() if brand else None

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//h1[@class="product-name"]/text()[normalize-space()]').extract()
        return title[0].strip() if title else None

    @staticmethod
    def _parse_sku(response):
        sku = is_empty(response.xpath('//span[@class="number"]/text()').extract())
        return sku.strip() if sku else None

    @staticmethod
    def _parse_categories(response):
        categories_sel = response.xpath('//ul[contains(@class, "bread-crumb")]/li/a/text()').extract()
        if categories_sel:
            categories = [i.strip() for i in categories_sel]
            return categories

    def _parse_price(self, response):
        currency = "CAD"
        price = is_empty(response.xpath('//div[contains(@class, "row-pricing")]'
                                        '//span[@class="reg-price-text"]/text()').extract())
        if not price:
            price = is_empty(response.xpath('//div[contains(@class, "row-pricing")]'
                                            '//span[@class="sale-price-text"]/text()').extract())
        try:
            price = float(price.replace("$", ''))
            return Price(price=price, priceCurrency=currency)
        except:
            self.log('Error while parsing price'.format(traceback.format_exc()), INFO)

    @staticmethod
    def _parse_image_url(response):
        image_url = is_empty(response.xpath('//div[@class="module-product-viewer"]'
                                            '//div[@class="item"]//img/@srcset').extract())
        return image_url

    @staticmethod
    def _parse_description(response):
        desc = response.xpath('//div[@class="row-product-description row"]/p[1]//text()').extract()
        if desc:
            return ''.join(desc)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        totals = response.xpath('//span[@class="result-total"]/text()').re('\d+')

        if totals:
            total_matches = int(totals[0])
        else:
            total_matches = 0
        return total_matches

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//div[@class="product-name-wrapper"]/a/@href').extract()

        if items:
            for item in items:
                res_item = SiteProductItem()
                yield urlparse.urljoin(response.url, item), res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        st = response.meta['search_term']
        total_matches = response.meta['total_matches']
        current_page = response.meta.get('current_page', 1)
        result_per_page = 48
        if total_matches and current_page < math.ceil(total_matches / float(result_per_page)):
            next_page = current_page + 1
            url = self.NEXT_URL.format(page_num=next_page * 48, search_term=st)
            return Request(
                url,
                meta={
                    'search_term': st,
                    'remaining': self.quantity,
                    'current_page': next_page,
                }
            )