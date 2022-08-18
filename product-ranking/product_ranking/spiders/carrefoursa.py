# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import re
import urlparse

from scrapy.conf import settings
from product_ranking.items import SiteProductItem, RelatedProduct, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, \
    FormatterWithDefaults, FLOATING_POINT_RGEX
from product_ranking.guess_brand import guess_brand_from_first_words


class CarrefoursaProductsSpider(BaseProductsSpider):
    name = 'carrefoursa_products'
    allowed_domains = ["www.carrefoursa.com"]

    SEARCH_URL = 'https://www.carrefoursa.com/tr/search/?text={search_term}'

    def __init__(self, *args, **kwargs):
        settings.overrides['USE_PROXIES'] = True
        super(CarrefoursaProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_product_links(self, response):
        products = response.xpath("//div[contains(@class, 'hover-box')]//a/@href").extract()
        for link in products:
            if link != '#':
                yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_link = response.xpath("//a[@class='pr-next']/@href").extract()
        if next_link:
            return next_link[0]

    def _scrape_total_matches(self, response):
        total = response.xpath("//div[contains(@class, 'total-pr-col')]/text() | "
                               "//span[@class='facet-pr-number']/text()").re('\d+')
        return int(total[0]) if total else None

    def parse_product(self, response):
        product = response.meta['product']
        cond_set_value(product, 'locale', 'fr_FR')

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        department = self._parse_department(response)
        cond_set_value(product, 'department', department)

        self._parse_price(response)

        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        return product

    def _parse_title(self, response):
        title = response.xpath("//div[@class='name']//h1/text()").extract()
        return title[0] if title else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        brand = response.xpath("//div[@class='brand']//span//a/text()").extract()
        if brand:
            brand = self._clean_text(brand[0])
        elif title:
            brand = guess_brand_from_first_words(title)
        return brand if brand else None

    def _parse_image_url(self, response):
        image = response.xpath("//a[@class='item']//img/@data-src").extract()
        return image[0] if image else None

    def _parse_description(self, response):
        span_desc = response.xpath("//div[@class='tab-details']//span/text()").extract()
        ul_desc = response.xpath("//div[@class='tab-details']//ul").extract()
        p_desc = response.xpath("//div[@class='tab-details']//p/text()").extract()

        ul_desc = ''.join(ul_desc)
        span_desc = ''.join(span_desc)
        p_desc = ''.join(p_desc)

        desc = span_desc + ul_desc + p_desc
        return self._clean_text(desc) if desc else None

    def _parse_currency(self, response):
        currency = response.xpath("//main/@data-currency-iso-code").extract()
        return currency[0] if currency else 'TRY'

    def _parse_price(self, response):
        product = response.meta['product']
        price_currency = self._parse_currency(response)
        price = response.xpath("//span[@class='item-price']/text()").re(FLOATING_POINT_RGEX)
        if price:
            cond_set_value(product, 'price',
                           Price(price=price[0].replace('.', '').replace(',', '.'),
                                 priceCurrency=price_currency))

    def _parse_categories(self, response):
        categories = response.xpath("//ol[@class='breadcrumb']//li//a/text()").extract()
        return categories if categories else None

    def _parse_department(self, response):
        categories = self._parse_categories(response)
        return categories[-1] if categories else None

    def _parse_reseller_id(self, response):
        reseller_id = re.search('p-(\d+)', self.product_url)
        return reseller_id.group(1) if reseller_id else None

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()