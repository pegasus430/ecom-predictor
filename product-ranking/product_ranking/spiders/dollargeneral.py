from __future__ import absolute_import, division, unicode_literals

import json
import re
from collections import OrderedDict

from scrapy.conf import settings
from scrapy.log import INFO, WARNING

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider, cond_set,
                                     cond_set_value)
from product_ranking.utils import extract_first, replace_http_with_https, _find_between
from product_ranking.validation import BaseValidator


class DollarGeneralProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'dollargeneral_products'
    allowed_domains = ["dollargeneral.com"]

    SEARCH_URL = "https://www.dollargeneral.com/catalogsearch/result/?q={search_term}"

    def __init__(self, *args, **kwargs):
        super(DollarGeneralProductsSpider, self).__init__(*args, **kwargs)
        self.headers = OrderedDict(
            [('Host', ''),
             ('Proxy-Connection', 'Keep-Alive Close'),
             ('Pragma', 'no-cache'),
             ('Accept-Encoding', 'gzip, deflate'),
             ('Accept-Language', 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4'),
             ('Upgrade-Insecure-Requests', '1'),
             ('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 '
                            '(KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'),
             ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'),
             ('Cache-Control', 'no-cache'),
             ('Connection', 'keep-alive')]
        )
        settings.overrides['USE_PROXIES'] = True
        settings.overrides['REFERER_ENABLED'] = False
        settings.overrides['COOKIES_ENABLED'] = False
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        middlewares['product_ranking.custom_middlewares.IncapsulaRequestMiddleware'] = 3
        middlewares['product_ranking.custom_middlewares.IncapsulaRetryMiddleware'] = 700
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares

        if self.product_url:
            self.product_url = replace_http_with_https(self.product_url)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        cond_set(
            product,
            'title',
            response.xpath("//meta[@property='og:title']/@content").extract())

        brand = self._parse_brand(response)
        product['brand'] = brand
        if not product.get('brand', None):
            brand = guess_brand_from_first_words(product.get('title', '').strip() if product.get('title') else '')
            cond_set_value(product, 'brand', brand)

        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)
        if categories:
            cond_set_value(product, 'department', categories[-1])

        price = self._parse_price(response)
        product['price'] = Price(price=float(price), priceCurrency='USD') if price else None

        in_store = self._parse_available_in_store(response)
        cond_set_value(product, 'is_in_store_only', in_store)

        is_out_of_stock = self._parse_stock_status(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        was_now = self._parse_was_now(response)
        cond_set_value(product, 'was_now', was_now)

        cond_set_value(product, 'promotions', bool(was_now))

        product['locale'] = "en-US"

        return product

    @staticmethod
    def _parse_available_in_store(response):
        if response.xpath(".//*[@class='available-instore']"):
            return True
        return False

    def _parse_was_now(self, response):
        old_price = response.xpath('//span[@data-price-type="oldPrice"]/@data-price-amount').extract()
        current_price = self._parse_price(response)
        if old_price and current_price:
            return ', '.join([current_price, old_price[0]])

    def _parse_categories(self, response):
        categories_list = response.xpath(
            "//div[contains(@class, 'breadcrumbs')]"
            "//a/text()"
        ).extract()
        categories = map(self._clean_text, categories_list)

        return categories if categories else None

    def _parse_brand(self, response):
        brand = response.xpath(
            "//div[@id='additional']//td[@data-th='Brand']/text()"
        ).extract()
        if brand:
            brand = self._clean_text(brand[0])

        return brand

    def _parse_price(self, response):
        price_info = response.xpath("//span[@class='price']/text()").extract()

        if price_info:
            price = price_info[0]
            if '$' in price:
                price = price.replace('$', '').strip()
            return price

    def _parse_image(self, response):
        image_url = ''
        try:
            image_info = _find_between(response.body, '"data": ', '"options"').strip()[:-1]
            image_info = json.loads(image_info)
        except:
            image_info = None

        if image_info:
            for image in image_info:
                if image.get('isMain'):
                    image_url = image.get('full', None)
                    break

        if not image_url:
            image_url = response.xpath("//meta[@property='og:image']/@content").extract()
            image_url = ''.join(image_url).strip()

        return image_url

    def _parse_stock_status(self, response):
        in_stock = response.xpath("//div[@title='Availability']//span/text()").extract()
        if in_stock and in_stock[0].lower() == 'in stock':
            return False
        return True

    @staticmethod
    def _parse_sku(response):
        return extract_first(
            response.xpath('//div[@class="value" and @itemprop="sku"]/text()')
        )

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = re.search(r'"productId":(\d+)', response.body)
        if reseller_id:
            return reseller_id.group(1)

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t\r]", "", text).strip()

    def _scrape_total_matches(self, response):
        total_info = response.xpath(
            "//span[@class='toolbar-number']/text()").extract()
        if total_info:
            total_matches = re.search('\d+', total_info[0]).group()
            return int(total_matches)

        return 0

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//ol[@class='products list items product-items']"
            "//li//div[@class='product-item-info']"
            "//a[contains(@class, 'product-item-photo')]/@href").extract()
        if links:
            for item_url in links:
                yield item_url, SiteProductItem()
        else:
            self.log("Found no product links in {url}".format(
                url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        url = response.xpath(
            "//*[@class='pages']"
            "//ul/li[contains(@class, 'current')]"
            "/following-sibling::li[1]/a/@href").extract()

        if url:
            return url[0]
        else:
            self.log("Found no 'next page' links", WARNING)
            return None
