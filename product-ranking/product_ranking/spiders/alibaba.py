from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback

from scrapy.http import Request

from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator
from urlparse import urljoin

class AlibabaProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'alibaba_products'
    allowed_domains = ["alibaba.com"]

    SEARCH_URL = 'https://www.alibaba.com/trade/search?fsb=y&IndexArea=product_en&CatId=&SearchText={search_term}&viewtype=G'

    SEARCH_API_URL = 'https://www.alibaba.com/trade/search?IndexArea=product_en&SearchText={search_term}&page={page_num}&atm=&viewtype=G&f0=y&async=y&waterfallReqCount=1&XPJAX=1'

    def start_requests(self):
        for req in super(AlibabaProductsSpider, self).start_requests():
            if not self.product_url:
                req = req.replace(
                    callback=self._parse_help)
            yield req

    def _parse_help(self, response):
        data = re.search(r'var _search_result_data = (.*?)page\.setPageData', response.body, re.DOTALL)
        try:
            data = json.loads(data.group(1))
        except:
            self.log('Parsing Error Search Data: {}'.format(traceback.format_exc()))
        else:
            product_links = [
                urljoin(response.url, i.get('productHref'))
                for i in data.get('normalList', [])
                if i.get('productHref')
                ]
            if not response.meta.get('total_matches'):
                response.meta['total_matches'] = int(data.get('util', {}).get('num', '0').replace(',', ''))
            api_url = urljoin(response.url, data.get('nextUrl')) if data.get('nextUrl') else None
            total_pages = data.get('pagination', {}).get('total')
            current_page = data.get('pagination', {}).get('current')
            next_link = data.get('pagination', {}).get('urlRule', '').format(current_page + 1) \
                if current_page < total_pages else None
            response.meta['next_link'] = urljoin(response.url, next_link) if next_link else None
            response.meta['current_page'] = current_page
            response.meta['prod_links'] = product_links if product_links else None
            if api_url:
                return Request(
                    api_url,
                    meta=response.meta,
                    dont_filter=True
                )
            else:
                return self.parse(response)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        
        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        buy_save_amount = self._parse_buy_save_amount(response)
        cond_set_value(product, 'buy_save_amount', buy_save_amount)

        cond_set_value(product, 'promotions', bool(buy_save_amount))

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        if categories:
            cond_set_value(product, 'department', categories[-1])

        minimum_order_quantity = self._parse_minimum_order_quantity(response)
        cond_set_value(product, 'minimum_order_quantity', minimum_order_quantity)

        model = self._parse_model(response)
        cond_set_value(product, 'model', model)

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//*[contains(@class, "ma-title") and @title]/@title').extract()
        return title[0] if title else None

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//dl[@class="do-entry-item" and contains(dt/span/text(), "Brand Name")]/dd/div/text()').extract()
        return brand[0] if brand else None

    @staticmethod
    def _parse_image(response):
        image = response.xpath('//meta[@property="og:image"]/@content').extract()
        return urljoin(response.url, image[0]) if image else None

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath('//*[@data-pid]/@data-pid').extract()
        return sku[0] if sku else None

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = re.search(r'(\d+)\.html', response.url)
        return reseller_id.group(1) if reseller_id else None

    def _parse_price(self, response):
        price = response.xpath('//span[@class="ma-ref-price"]/span/text()').re(FLOATING_POINT_RGEX)
        currency = response.xpath('//meta[@property="og:price:currency"]/@content').extract()
        currency = currency[0] if currency else 'USD'
        if not price:
            price = response.xpath('//meta[@property="og:price:standard_amount"]/@content').extract()
        try:
            return Price(price=float(price[0].replace(',', '')), priceCurrency=currency) if price else None
        except:
            self.log('Error Parsing Price Issue: {}'.format(traceback.format_exc()))

    @staticmethod
    def _parse_minimum_order_quantity(response):
        minimum_order_quantity = response.xpath('//span[@class="ma-min-order"]').re('\d+')
        return int(minimum_order_quantity[0]) if minimum_order_quantity else None

    @staticmethod
    def _parse_buy_save_amount(response):
        old_price = response.xpath('//meta[@property="og:price:standard_amount"]/@content').extract()
        current_price = response.xpath('//meta[@property="og:price:amount"]/@content').extract()
        amount = response.xpath('//ul[contains(@class, "ma-ladder-price")]'
                                '//span[@class="ma-quantity-range"]'
                                '/@title').re('>=(\d+)')
        if all([old_price, current_price, amount]):
            return amount[-1] if old_price[0] != current_price[0] else None

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//*[@itemtype="http://schema.org/BreadcrumbList"]/li[not(position()=1)]'
                                    '//span[@itemprop="name"]/text()').extract()
        categories = [i.strip() for i in categories if i.strip()]
        bread_count = response.xpath('///*[@itemtype="http://schema.org/BreadcrumbList"]'
                                     '/li[position()=last()]'
                                     '//span[@class="bread-count"]/text()').extract()
        if bread_count and categories:
            categories[-1] = ''.join([categories[-1], bread_count[0]])
        return categories

    @staticmethod
    def _parse_model(response):
        model = response.xpath('//dl[@class="do-entry-item" and contains(dt/span/text(), "Model Number")]/dd/div/text()').extract()
        return model[0] if model else None

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body)
            product_links = [
                urljoin(response.url, i.get('productHref'))
                for i in data.get('normalList', [])
                if i.get('productHref')
                ]
        except:
            self.log('Not products in json: {}'.format(traceback.format_exc()))
            product_links = []
        product_links = response.meta.get('prod_links', []) + product_links
        for link in product_links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if response.meta.get('next_link'):
            return Request(response.meta.get('next_link'), meta=response.meta, callback=self._parse_help, dont_filter=True)
