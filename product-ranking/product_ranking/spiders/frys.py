# coding=utf-8
from __future__ import absolute_import, division, unicode_literals

import re
from urlparse import urljoin
from scrapy.conf import settings
from scrapy.log import INFO

from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator


class FrysProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'frys_products'
    allowed_domains = ["frys.com"]

    BASE_URL = "http://frys.com"
    SEARCH_URL = "http://www.frys.com/search?search_type=regular&sqxts=1&cat=&query_string={search_term}&nearbyStoreName=false"
    current_page = 1

    def __init__(self, *args, **kwargs):
        super(FrysProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse category
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Parse upc
        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc)

        # Parse model
        model = self._parse_model(response)
        cond_set_value(product, 'model', model)

        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        is_out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        return product

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath('//div[@id="ProductAttributes"]/ui/li[1]/text()').extract()
        if sku:
            sku = sku[0]
            sku = re.findall(r'(?<=#)\w+', sku)
            if sku:
                return sku[0].strip()

    @staticmethod
    def _parse_upc(response):
        upc = response.xpath('//div[@id="ProductAttributes"]/ui/li[3]/text()').re(r'(?<=#)\w+')
        if upc:
            return upc[0].strip()

    @staticmethod
    def _parse_model(response):
        model = response.xpath('//div[@id="ProductAttributes"]/ui/li[4]/text()').extract()
        if model:
            model = model[0]
            model = re.findall(r'(?<=#).+', model)
            if model:
                return model[0].strip()

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//label[@class="product_title"]/b/text()').extract()
        if title:
            return title[0].strip()

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//title/text()').extract()
        if brand:
            try:
               return brand[0].split('|')[1].strip()
            except:
                return

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//div[@id="product_bread_crums"]/b/a/text()').extract()
        if categories:
            categories = [category.strip() for category in categories]
            return categories[1:]

    @staticmethod
    def _parse_price(response):
        currency = "USD"
        price = response.xpath('//label[contains(@id, "l_price1_value")]/text()').re(r'[\d\.\,]+')
        if price:
            price = price[0].replace(',', '')
            try:
                price = float(price)
            except:
                price = 0
            return Price(price=price, priceCurrency=currency)

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath('//div[@id="large_image"]/a/img/@src').extract()
        if image_url:
            image_url = image_url[0]
            return image_url

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = re.search(r'product\/(\d+)', response.url)
        return reseller_id.group(1) if reseller_id else None

    def _parse_is_out_of_stock(self, response):
        in_stock = response.xpath('//div[@id="product_shipping_info"]//text()').re('In Stock')
        return False if in_stock else True

    @staticmethod
    def _scrape_total_matches(response):
        totals = response.xpath('//h6/span[2]/text()').re(r'\d+')
        if totals:
            return int(totals[-1])

    @staticmethod
    def _scrape_total_pages(response):
        pages = response.xpath('//div[contains(text(), "Page")]/text()').re(r'\d+')
        if pages:
            return int(pages[-1])

    def _scrape_product_links(self, response):
        items = response.xpath('//div[@id="prodCol"]/div[2]/p/small/b/a/@href').extract()
        if items:
            for item in items:
                item = urljoin(self.BASE_URL, item)
                res_item = SiteProductItem()
                yield item, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        self.current_page +=1
        next_page = response.xpath('//ul[@id="pageNumber"]//a[contains(text(), "'+str(self.current_page)+'")]/@href').extract()
        if not next_page:
            next_page = response.xpath('//ul[@id="pageNumber"]//a[contains(text(), "»")]/@href').extract()
        if next_page:
            next_page = urljoin(self.BASE_URL, next_page[0])
            return next_page


