from __future__ import division

import math
import re
import string
import traceback
from collections import OrderedDict

import yaml
from scrapy import Request
from scrapy.conf import settings
from scrapy.log import INFO

from product_ranking.items import Price, SiteProductItem
from product_ranking.powerreviews import parse_powerreviews_buyer_reviews
from product_ranking.spiders import (FLOATING_POINT_RGEX, BaseProductsSpider,
                                     cond_set_value)
from product_ranking.utils import extract_first, replace_http_with_https


class ToysrusProductsSpider(BaseProductsSpider):
    name = 'toysrus_products'
    allowed_domains = ["toysrus.com", "readservices-b2c.powerreviews.com"]

    SEARCH_URL = "https://www.toysrus.com/search?q={search_term}"

    REVIEW_URL = "http://readservices-b2c.powerreviews.com/m/{pwr_merchantId}/l/en_US/product/{pwr_productId}" \
                  "/reviews?apikey={api_key}"

    PRODUCT_URL = "https://www.toysrus.com/product?productId={productId}&cat=1"
    current_page = 1

    COOKIE = {'_br_uid_2': 'uid%3D6370947881333%3Av%3D12.0%3Ats%3D1502066870648%3Ahc%3D105;'}

    def __init__(self, *args, **kwargs):
        super(ToysrusProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        self.headers = OrderedDict(
            [('Host', ''),
             ('Accept-Encoding', 'gzip, deflate'),
             ('Accept-Language', 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4'),
             ('User-Agent', '(Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36'),
             ('Accept','text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'),
             ('Connection', 'keep-alive')]
        )
        settings.overrides['USE_PROXIES'] = True
        settings.overrides['REFERER_ENABLED'] = False
        settings.overrides['COOKIES_ENABLED'] = False
        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares
        if self.product_url and 'index.jsp' in self.product_url:
            self.product_url = self.product_url.replace('/index.jsp', '')
        if self.product_url:
            self.product_url = replace_http_with_https(self.product_url)
        self.user_agent = "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)"

    def start_requests(self):
        for request in super(ToysrusProductsSpider, self).start_requests():
            if self.searchterms:
                request = request.replace(cookies=self.COOKIE, callback=self.parse_redirect)
            yield request

    def parse_redirect(self, response):
        if 'totalCount' in response.body_as_unicode():
            return self.parse(response)
        else:
            prod = SiteProductItem()
            prod['url'] = response.url
            prod['search_term'] = response.meta['search_term']
            prod['total_matches'] = 1
            response.meta['product'] = prod
            return self.parse_product(response)

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_GB'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # Parse department
        department = self._parse_department(response)
        cond_set_value(product, 'department', department)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse stock status
        is_out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        shipping = self._parse_shipping(response)
        cond_set_value(product, 'shipping', shipping)

        # Parse upc
        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # reseller_id
        cond_set_value(product, 'reseller_id', sku)

        product_id = re.search(r'productId=(.*?)\"', response.body)
        pwr_apiKey = re.search(r'\"apiKey\":\"(.*?)\",', response.body)
        pwr_merchantId = re.search(r'\"merchantID\":(.*?)[,\}]', response.body)
        if pwr_apiKey and pwr_merchantId and product_id and not self.summary:
            return Request(
                url=self.REVIEW_URL.format(
                    pwr_merchantId=pwr_merchantId.group(1),
                    pwr_productId=product_id.group(1),
                    api_key=pwr_apiKey.group(1)
                ),
                callback=self._parse_buyer_reviews,
                meta=meta
            )
        else:
            return product

    def _parse_title(self, response):
        title = extract_first(response.xpath('//div[contains(@class, "product-title")]/@title | '
                                             '//h1[contains(@class, "product-item__product-title")]/@title'))
        return title

    def _parse_brand(self, response):
        brand = re.search('"brandName":"(.*?)",', response.body)
        if brand:
            return brand.group(1)

    def _parse_department(self, response):
        department = self._parse_categories(response)
        if department:
            return department[-1]

    @staticmethod
    def _parse_shipping(response):
        shipping_text = ''.join(
            response.xpath('//span[contains(@class, "promo-desc")]/text()').extract())
        if 'FREE Shipping' in shipping_text:
            return True
        return False

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath("//*[contains(@class,'breadcrumb')]/li/a/text()").extract()
        return categories

    def _parse_price(self, response):
        # Sale price
        price = re.search('"salePrice":(.*?),', response.body)
        price = price.group(1) if price else None
        if not price:
            price = response.xpath('.//*[@class="prices"]/span[@class="sale-price"]/text()').re(FLOATING_POINT_RGEX)
            price = price[0] if price else None
        if not price:
            price = response.xpath('.//*[@class="prices"]/span[@class="price"]/text()').re(FLOATING_POINT_RGEX)
            price = price[0] if price else None
        if not price:
            price = response.xpath('//input[@id="productListPrice"]/@value').extract()
            price = price[0] if price else None
        try:
            return Price(price=float(price.replace(',', '.')), priceCurrency='USD')
        except:
            self.log('Price error: {}'.format(traceback.format_exc()))

    def _parse_image_url(self, response):
        image_url = extract_first(response.xpath('//div[contains(@class, "gallery-thumbnails")]/img/@src'))
        return image_url

    def _parse_is_out_of_stock(self, response):
        stock_status = re.search('"actionType":"(.*?)"', response.body)
        if stock_status and stock_status.group(1) == 'OUT_OF_STOCK':
            return True
        return False

    def _parse_upc(self, response):
        upc = re.search('"upcNumber":"(.*?)",', response.body)
        if upc:
            return upc.group(1).zfill(12)

    @staticmethod
    def _parse_sku(response):
        sku = re.search('"SKU":"(.*?)",', response.body)
        if sku:
            return sku.group(1)

    def _parse_buyer_reviews(self, response):
        meta = response.meta
        product = meta['product']
        cond_set_value(product, 'buyer_reviews', parse_powerreviews_buyer_reviews(response))
        return product

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        total_matches = re.search('"totalCount":(\d+),', response.body)
        total_matches = total_matches.group(1) if total_matches else None
        if not total_matches:
            total_matches = response.xpath('//script[@type="text/javascript"]/text()').re('"totalCount":(\d+)')
            total_matches = total_matches[0] if total_matches else None
        if not total_matches:
            total_matches = response.xpath('//script[@type="text/javascript"]/text()').re('totalRecords\((\d+)\)')
            total_matches = total_matches[0] if total_matches else None
        if total_matches:
            return int(total_matches)
        else:
            return 0

    def _scrape_results_per_page(self, response):
        results_per_page = response.xpath('//script[@type="text/javascript"]/text()').re('var totalProd = \'(\d+)\'')
        if not results_per_page:
            results_per_page = response.xpath('//script[@type="text/javascript"]/text()').re('"perPage":(\d+)')
        if results_per_page:
            return int(results_per_page[0])
        else:
            return 0

    def _scrape_product_links(self, response):
        try:
            json_data = yaml.safe_load(
                re.search(
                    'window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s+?window\.__CONFIG__',
                    response.body_as_unicode()
                ).group(1)
            )
        except:
            self.log('Can not extract json data: {}'.format(traceback.format_exc()))
        else:
            items = json_data.get('products', {}).get('entities')
            if items and isinstance(items, list):
                for item in items:
                    productId = item.get('productId')
                    product_url = self.PRODUCT_URL.format(productId=productId)
                    product_item = SiteProductItem()
                    yield product_url, product_item
            else:
                self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        total_matches = self._scrape_total_matches(response)
        results_per_page = self._scrape_results_per_page(response)
        if not results_per_page:
            results_per_page = 24
        if (total_matches and results_per_page
            and self.current_page < math.ceil(total_matches / float(results_per_page))):
            self.current_page += 1
            search_term = response.meta.get('search_term')
            offset = '&page={}'.format(self.current_page)
            url = self.SEARCH_URL.format(search_term=search_term) + offset
            return url
