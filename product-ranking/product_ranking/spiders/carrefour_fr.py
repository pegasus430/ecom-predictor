# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback
import urlparse

from collections import OrderedDict
from scrapy.http import Request
from scrapy.conf import settings
from product_ranking.items import SiteProductItem, RelatedProduct, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, \
    FormatterWithDefaults, FLOATING_POINT_RGEX
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi


class CarrefourProductsSpider(BaseProductsSpider):
    name = 'carrefour_fr_products'
    allowed_domains = ["carrefour.fr", "rueducommerce.fr", "prod.ecatalgoapi.monkees.pro",
                       "www.carrefourlocation.fr"]
    current_page = 0
    results_per_page = 20

    SEARCH_URL = 'http://www.carrefour.fr/search/site/{search_term}/31?page={page_num}&can_redirect=1'

    ORIGINAL_API_URL = 'https://prod.ecatalgoapi.monkees.pro/v1/product/{prod_info}' \
                       '/catalog/{carrefour_info}/v01'

    handle_httpstatus_list = [500, 502, 503, 504, 400, 403, 408, 429]

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi()
        url_formatter = FormatterWithDefaults(page_num=self.current_page)
        super(CarrefourProductsSpider, self).__init__(
            url_formatter=url_formatter,
            site_name=self.allowed_domains[0],
            *args, **kwargs)

        self.headers = OrderedDict(
            [('Host', ''),
             ('Proxy-Connection', 'Keep-Alive Close'),
             ('Pragma', 'no-cache'),
             ('Accept-Encoding', 'gzip, deflate'),
             ('Accept-Language', 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4'),
             ('Upgrade-Insecure-Requests', '1'),
             ('User-Agent',
              'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'),
             ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'),
             ('Cache-Control', 'no-cache'),
             ('Connection', 'keep-alive')]
        )

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        middlewares['product_ranking.custom_middlewares.IncapsulaRequestMiddleware'] = 3
        middlewares['product_ranking.custom_middlewares.IncapsulaRetryMiddleware'] = 700
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares

        retry_codes = settings.get('RETRY_HTTP_CODES')
        retry_codes = [c for c in retry_codes if c not in self.handle_httpstatus_list]
        settings.overrides['RETRY_HTTP_CODES'] = retry_codes

        settings.overrides['RETRY_HTTP_CODES'] = [500, 502, 503, 504, 400, 403, 408, 429]
        settings.overrides['USE_PROXIES'] = True

    def start_requests(self):
        for request in super(CarrefourProductsSpider, self).start_requests():
            meta = request.meta.copy()
            meta['results_per_page'] = self.results_per_page
            request = request.replace(meta=meta, dont_filter=True)
            if not self.product_url:
                request = request.replace(method='POST')
            yield request

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_product_links(self, response):
        st = response.meta.get('search_term')
        products = response.xpath('//div[@class="k4-productitem-content"]'
                                  '//a[contains(@class, "k4-js-dotdotdot")]/@href').extract()
        for prod_link in products:
            yield prod_link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        st = response.meta.get('search_term')
        results_per_page = response.meta.get('results_per_page')
        self.current_page += 1
        total = self._scrape_total_matches(response)
        if total and self.current_page * results_per_page >= total:
            return

        return Request(
            url=self.SEARCH_URL.format(search_term=st, page_num=self.current_page),
            method='POST',
            dont_filter=True,
            meta=response.meta
        )

    def _scrape_total_matches(self, response):
        total = response.xpath("//div[contains(@class, 'k4-managesearch-cell')]/@data-result").re('\d+')
        return int(total[0]) if total else None

    def parse_product(self, response):
        product = response.meta['product']
        cond_set_value(product, 'locale', 'fr_FR')
        if 'www.carrefour.fr' in response.url:
            carrefour_info = re.search('carrefour/(.*?)\/', response.url)
            prod_info = re.search('produit/(.*?)\?', response.url)
            if prod_info and carrefour_info:
                prod_info = prod_info.group(1)
                carrefour_info = carrefour_info.group(1)
                return Request(
                    self.ORIGINAL_API_URL.format(prod_info=prod_info,
                                                 carrefour_info=carrefour_info),
                    meta=response.meta,
                    headers={'customer': 'carrefour'},
                    callback=self._parse_origin_product
                )

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

        return product

    def _parse_title(self, response):
        title = response.xpath("//div[@class='productDetails']//*[@itemprop='name']/text() | "
                               "//div[contains(@class, 'visible-xs')]//div[@class='title-holder']//h2/text() | "
                               "//h1[@class='product-title']/text() | "
                               "//div[@class='productHead']//h1[@class='heading']//span/text()  ").extract()
        return self._clean_text(' '.join(title)) if title else None

    def _parse_brand(self, response):
        brand = response.xpath("//span[@itemprop='brand']/text() | "
                               "//span[@itemprop='brand']//span/text()").extract()
        if brand:
            brand = self._clean_text(brand[0])
        else:
            brand = re.search('product_brand":(.*?),', response.body)
            if brand:
                brand = brand.group(1).replace('"', '')
        return brand if brand else None

    def _parse_image_url(self, response):
        image = response.xpath("//div[@class='photoContainer']//img/@src | "
                               "//a[contains(@class, 'main-visual-link')]//img/@src | "
                               "//div[contains(@class, 'principal-slider')]//img/@src | "
                               "//div[@class='productMain']//img/@src").extract()
        return urlparse.urljoin(response.url, image[0]) if image else None

    def _parse_description(self, response):
        description = response.xpath("//div[@id='blocDescriptionContent']//p/text()").extract()
        if not description:
            description = response.xpath("//div[@id='blocDescriptionContent']/text() | "
                                         "//div[@itemprop='description']/text() | "
                                         "//div[contains(@class, 'info-text')]//p/text()").extract()
        return self._clean_text(''.join(description)) if description else None

    def _parse_currency(self, response):
        currency = response.xpath("//meta[@itemprop='priceCurrency']/@content").extract()
        return currency[0] if currency else 'EUR'

    def _parse_price(self, response):
        product = response.meta['product']
        price_currency = self._parse_currency(response)
        price = response.xpath("//*[@itemprop='price']/@content | "
                               "//div[contains(@class, 'visible-xs')]//span[@class='price']/text()").re(FLOATING_POINT_RGEX)
        if price:
            cond_set_value(product, 'price',
                           Price(price=price[0].replace(',', '.'),
                                 priceCurrency=price_currency))

    def _parse_categories(self, response):
        categories = response.xpath("//a[@itemprop='item']//span/text() | "
                                    "//span[@itemprop='title']/text() | "
                                    "//div[@id='breadCrumbZone']//a/text()").extract()
        return categories if categories else None

    def _parse_department(self, response):
        categories = self._parse_categories(response)
        return categories[-1] if categories else None

    def _parse_origin_product(self, response):
        product = response.meta.get('product')
        try:
            data = json.loads(response.body)
            title = data.get('name')
            product['title'] = title
            price = data.get('striked_price')
            price = Price(price=price, priceCurrency='EUR')
            product['price'] = price
            description = data.get('description1')
            product['description'] = description
            if data.get('images', {}).get('elements'):
                image = data.get('images', {}).get('elements')[0].get('big')
                product['image_url'] = image
            brand = data.get('mark')
            product['brand'] = brand
        except:
            self.log('Error while parsing json data {}'.format(traceback.format_exc()))

        return product

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()