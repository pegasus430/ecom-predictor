from __future__ import division, absolute_import, unicode_literals

import base64
import traceback
import urllib

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty
from scrapy.conf import settings
from scrapy.http import Request
from scrapy.log import WARNING


class CostCoBusinessDeliveryProductsSpider(BaseProductsSpider):
    name = 'costcobusinessdelivery_products'
    allowed_domains = ["www.costcobusinessdelivery.com"]
    SEARCH_URL = 'https://www.costcobusinessdelivery.com/CatalogSearch?dept=All&keyword={search_term}&pageSize=96'

    def __init__(self, zip_code='95045', *args, **kwargs):
        self.zip_code = zip_code
        self.zip_cookie = {
            'WC_BD_ZIP': self.zip_code
        }
        super(CostCoBusinessDeliveryProductsSpider, self).__init__(
            *args,
            **kwargs
        )

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 " \
                          "(KHTML, like Gecko) Chrome/64.0.3282.186 Safari/537.36"

    def start_requests(self):
        for request in super(CostCoBusinessDeliveryProductsSpider, self).start_requests():
            request = request.replace(cookies=self.zip_cookie)
            if not self.product_url:
                st = request.meta.get('search_term')
                request = request.replace(url=self.SEARCH_URL.format(search_term=urllib.quote_plus(st.encode('utf-8'))),
                                          meta={'search_term': st, 'remaining': self.quantity},
                                          )
            yield request

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _get_products(self, response):
        for request in super(CostCoBusinessDeliveryProductsSpider, self)._get_products(response):
            yield request.replace(dont_filter=True)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(response)
        if not brand and title:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        department = self._parse_department(response)
        product['department'] = department

        model = self._parse_model(response)
        cond_set_value(product, 'model', model)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)
        cond_set_value(product, 'reseller_id', sku)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        oos = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', oos)

        product["upc"] = None

        product['locale'] = "en-US"

        return product

    def _parse_title(self, response):
        title = response.xpath('//h1[@itemprop="name"]/text()').extract()
        return title[0] if title else None

    @staticmethod
    def _parse_brand(response):
        return is_empty(response.xpath('//div[preceding-sibling::div[text()="Brand"]]'
                                       '/text()').extract())

    @staticmethod
    def _parse_image(response):
        image_url = response.xpath('//img[@itemprop="image"]/@src').extract()
        return is_empty(image_url)

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//ul[@id="crumbs_ul"]/li/a/text()').extract()
        return categories[1:] if categories else None

    def _parse_department(self, response):
        categories = self._parse_categories(response)
        return categories[-1] if categories else None

    @staticmethod
    def _parse_model(response):
        model = response.xpath('//span[@itemprop="sku"]/text()').extract()
        return model[0].strip() if model else None

    def _parse_sku(self, response):
        sku = response.xpath('//span[@itemprop="sku"]/text()').extract()
        return sku[0] if sku else None

    def _parse_price(self, response):
        price = response.xpath('//span[contains(@class, "value")]/text()').extract()
        try:
            deliver_price = float(base64.b64decode(price[0]).replace(',', ''))
            if response.xpath('//span[@class="minus"]'):
                less_price = float(base64.b64decode(price[1]).replace(',', ''))
                deliver_price = deliver_price - less_price
            return Price(price=deliver_price, priceCurrency='USD')
        except:
            self.log('Error Parsing Price Issue: {}'.format(traceback.format_exc()))

    def _parse_out_of_stock(self, response):
        oos = response.xpath('//div[@class="form-group"]//ul//li'
                             '//input[@id="add-to-cart-btn"]/@value').extract()
        if oos and oos[0] == 'Out of Stock':
            return True
        return False

    def _scrape_product_links(self, response):
        product_links = response.xpath('//div[@data-pdp-url]/@data-pdp-url').extract()

        if not product_links:
            self.log("Found no product links.", WARNING)

        for link in product_links:
            yield link, SiteProductItem()

    def _scrape_total_matches(self, response):
        totals = response.xpath('//h1[@id="rsltCntMsg"]/text()').re('\d+')
        return int(totals[0]) if totals else None

    def _scrape_next_results_page_link(self, response):
        next_url = response.xpath('//li[@class="forward"]/a/@href').extract()
        if next_url:
            return Request(
                url=next_url[0],
                meta=response.meta,
                cookies=self.zip_cookie
            )

    def _get_products(self, response):
        for req in super(CostCoBusinessDeliveryProductsSpider, self)._get_products(response):
            if isinstance(req, Request):
                req = req.replace(cookies=self.zip_cookie,
                                  callback=self.parse_product)
            yield req
