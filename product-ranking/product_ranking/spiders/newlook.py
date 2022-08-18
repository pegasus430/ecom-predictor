from __future__ import division, absolute_import, unicode_literals
import string
import urlparse
import json
import re
import traceback

from scrapy.log import ERROR, WARNING, INFO
from scrapy.http import Request

from product_ranking.utils import is_empty
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set, \
    cond_set_value, FormatterWithDefaults


class NewlookProductsSpider(BaseProductsSpider):
    name = 'newlook_products'

    allowed_domains = ["newlook.com"]

    start_urls = []

    SEARCH_URL = 'http://www.newlook.com/row/search/results/data-48.json?' \
                 'currency=EUR&language=en&page={pagenum}' \
                 '&q={search_term}:{sort_mode}' \
                 '&sort={sort_mode}&text={search_term}'

    BASE_URL = 'http://www.newlook.com/row'
    IMG_RESIZE = '?strip=true&qlt=80&w=1024'

    SORTING = None
    SORT_MODES = {
        'default': 'relevance',
        'price_low_to_high': 'price-asc',
        'price_high_to_low': 'price-desc',
        'newest': 'newest',
        'best_sellers': 'bestSeller',
    }

    def __init__(self, sort_mode=None, *args, **kwargs):
        if sort_mode:
            if sort_mode.lower() not in self.SORT_MODES:
                self.log('"%s" not in SORT_MODES')
            else:
                self.SORTING = self.SORT_MODES[sort_mode.lower()]

        super(NewlookProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                pagenum=0,
                sort_mode=self.SORTING or self.SORT_MODES['default']),
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        # title
        cond_set(
            product,
            'title',
            response.xpath(
                '//h2[@itemprop="name"]/text()'
            ).extract(),
            conv=string.strip)

        # brand
        if not product.get('brand', None):
            brand = guess_brand_from_first_words(
                product.get('title', '').strip())
            if brand:
                product['brand'] = brand

        # image_url
        cond_set(
            product,
            'image_url',
            response.xpath(
                '//meta[@itemprop="image"]/@content'
            ).extract(),
            lambda url: urlparse.urljoin(response.url, url + self.IMG_RESIZE)
        )

        # description
        description = is_empty(response.xpath(
                '//div[@itemprop="description"]').extract())
        cond_set_value(product, 'description', description)

        # sku
        cond_set(
            product,
            'sku',
            response.xpath(
                '//meta[@itemprop="sku"]/@content'
            ).extract(),
        )

        # category
        category = self._parse_category(response)
        cond_set_value(product, 'category', category)
        if category:
            department = category[-1]
            cond_set_value(product, 'department', department)

        # price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # special pricing
        special_pricing = re.search('previousPrice', response.body)
        cond_set_value(product, 'special_pricing', special_pricing, conv=bool)

        cond_set_value(product, 'locale', 'en_EU')

        return product

    def _parse_category(self, response):
        category = response.xpath(
            '//div[@class="breadcrumb"]//span[@property="name"]/text()'
        ).extract()

        if category:
            category = category[1:]

        return category

    def _parse_price(self, response):
        price = is_empty(
            response.xpath(
                '//meta[@itemprop="price"]/@content'
            ).extract(), 0.00
        )

        currency = is_empty(
            response.xpath(
                '//meta[@itemprop="priceCurrency"]/@content'
            ).extract()
        )

        return Price(
            price=price,
            priceCurrency=currency
        )

    def _scrape_total_matches(self, response):
        total_matches = None
        try:
            js = json.loads(response.body_as_unicode())
        except ValueError:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
        else:
            total_matches = js.get('data', {}).get('pagination', {}).get('totalNumberOfResults', 0)

        return total_matches

    def _scrape_product_links(self, response):
        try:
            js = json.loads(response.body_as_unicode())
        except ValueError:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)

        links = [result.get('url') for result in js.get('data', {})
                .get('results', {}) if result.get('url')]

        for link in links:
            yield self.BASE_URL + link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        try:
            js = json.loads(response.body_as_unicode())
        except ValueError:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)

        try:
            pagination = js['data']['pagination']
        except:
            self.log('Invalid JSON', ERROR)

        cur_page = pagination.get('currentPage')
        max_pages = pagination.get('numberOfPages')
        if cur_page is not None and max_pages:
            if cur_page + 1 >= max_pages:
                return None

            search_term = response.meta.get('search_term')
            return self.url_formatter.format(self.SEARCH_URL,
                                             search_term=search_term,
                                             pagenum=cur_page + 1)
