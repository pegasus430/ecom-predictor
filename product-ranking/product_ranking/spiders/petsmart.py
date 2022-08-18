# -*- coding: utf-8 -*-
import string
import json
import re
import traceback

from scrapy import Request
from scrapy.conf import settings
from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import cond_set_value, FLOATING_POINT_RGEX
from product_ranking.spiders.contrib.product_spider import ProductsSpider
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi


def _populate(item, key, value, first=False):
    if not value:
        return
    value = filter(None, map(string.strip, value))
    if value:
        if first:
            item[key] = value[0]
        else:
            item[key] = value


class PetsmartProductsSpider(ProductsSpider):
    name = 'petsmart_products'
    allowed_domains = ['petsmart.com', 'api.bazaarvoice.com']

    SEARCH_URL = 'http://www.petsmart.com/search?SearchTerm={search_term}'

    XPATH = {
        'product': {
            'title': '//h1[contains(@class, "product-name")]/text()',
            'categories': '//div[@class="breadcrumb-wrapper"]/a/@href',
            'currency': '//meta[@property="og:price:currency"]/@content',
            'price': '//meta[@property="og:price:amount"]/@content',
            'out_of_stock_button': '//meta[@property="og:availability"]/@content',
            'id': '//input[@id="parentSKU"]/@value',
            'sku': '//input[@id="productID"]/@value',
            'size': '//ul[@class="swatches size"]//a/@data-variant-value',
            'color': '//ul[@class="swatches color"]//a/@data-variant-value',
            'variants': '//li[contains(@class, "ws-variation-list-item")]/@data-sku',
        },
        'search': {
            'total_matches': '//*[contains(@class, "product-tab")]/text()',
            'next_page': '//li[@class="current-page"]/following-sibling::li/a/@href',
            'prod_links': '//ul[contains(@class,"search-result-items")]/li/a/@href',
        },
    }

    REVIEWS_URL = "https://api.bazaarvoice.com/data/batch.json?passkey=208e3foy6upqbk7glk4e3edpv&apiversion=5.5&" \
                  "displaycode=4830-en_us&resource.q0=products&filter.q0=id%3Aeq%3A{product_id}&stats.q0=reviews"

    IMAGE_URL = 'http://s7d2.scene7.com/is/image/PetSmart/{sku}_Imageset'

    MAIN_IMAGE_URL = 'http://images.petsmartassets.com/is/image/PetSmart/{}?fmt=jpg'

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)
        super(PetsmartProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        reqs = []

        # locale
        product['locale'] = 'en_US'

        # title
        title = response.xpath(self.XPATH['product']['title']).extract()
        _populate(product, 'title', title, first=True)

        # categories
        categories = response.xpath(self.XPATH['product']['categories']).extract()
        if categories:
            if categories[0][-1] == '/':
                categories = categories[0][:-1].replace('http://www.petsmart.com/', '').split('/')
            else:
                categories = categories[0].replace('http://www.petsmart.com/', '').split('/')
        _populate(product, 'categories', categories)
        if product.get('categories'):
            product['department'] = product['categories'][-1]

        # image url
        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # variants
        variants = set(response.xpath(self.XPATH['product']['variants']).extract())

        if len(variants) > 1:
            product['variants'] = []
            response.meta['product'] = product
            variant_sku = variants.pop()
            response.meta['variants'] = variants
            reqs.append(
                Request(
                    response.url.split('?')[0].split(';')[0] + '?var_id=' + variant_sku,
                    meta=response.meta,
                    callback=self._parse_variants,
                )
            )
        else:
            product['variants'] = [self._parse_variant_data(response)]

        # buyer_reviews
        product_id = re.findall(r'configData.productId\s+=\s+\"(.+)\";', response.body_as_unicode())
        if product_id:
            reqs.append(
                Request(
                    self.REVIEWS_URL.format(product_id=product_id[0]),
                    self._parse_buyer_reviews,
                    meta={'product': product}
                )
            )

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_price(self, response):
        sale_price = response.xpath(
            "//div[@class='ship-to-me-price']"
            "//div[@class='product-price']"
            "//span[@class='price-sales']/text()"
        ).re(FLOATING_POINT_RGEX)

        regular_price = response.xpath(
            "//div[@class='ship-to-me-price']"
            "//div[@class='product-price']"
            "//span[@class='price-regular']/text()"
        ).re(FLOATING_POINT_RGEX)

        standard_price = response.xpath(
            "//div[@class='ship-to-me-price']"
            "//div[@class='product-price']"
            "//span[@class='price-standard']/text()"
        ).re(FLOATING_POINT_RGEX)

        if sale_price:
            final_price = sale_price[0]
        elif regular_price:
            final_price = regular_price[0]
        elif standard_price:
            final_price = standard_price[0]
        else:
            final_price = None

        currency = 'USD'
        try:
            return Price(price=float(final_price), priceCurrency=currency)
        except Exception as e:
            self.log('Price error {}'.format(traceback.format_exc(e)))

    def _parse_brand(self, response):
        brand = response.xpath('//span[@itemprop="brand"]//text()').extract()
        if not brand:
            brand = response.xpath('//span[@class="brand-by"]//a/text()').extract()
        return brand[0].strip() if brand else None

    def _parse_image(self, response):
        try:
            prod_id = int(re.findall(r'\d+', response.xpath("//*[@id='productID']/@value").extract()[0])[0])
            return self.MAIN_IMAGE_URL.format(prod_id)
        except Exception as e:
            self.log('Price error {}'.format(traceback.format_exc(e)))

    def _parse_variants(self, response):
        response.meta['product']['variants'].append(
            self._parse_variant_data(response)
        )
        if response.meta.get('variants'):
            variant_sku = response.meta['variants'].pop()
            return Request(
                response.url.split('?')[0] + '?var_id=' + variant_sku,
                meta=response.meta,
                callback=self._parse_variants,
            )
        else:
            if reqs:
                return self.send_next_request(reqs, response)

            return response.meta['product']

    def _parse_variant_data(self, response):
        data = {}
        # id
        id = response.xpath(self.XPATH['product']['id']).extract()
        _populate(data, 'id', id, first=True)

        # sku
        sku = response.xpath(self.XPATH['product']['sku']).extract()
        _populate(data, 'sku', sku, first=True)

        # image url
        if data.get('sku'):
            image_url = [self.IMAGE_URL.format(sku=data['sku'])]
        else:
            image_url = [""]
        _populate(data, 'image_url', image_url, first=True)

        # in stock?
        stock = response.xpath(self.XPATH['product']['out_of_stock_button']).extract()
        data['is_out_of_stock'] = False
        if stock:
            if re.search('in stock', stock[0], re.IGNORECASE):
                data['is_out_of_stock'] = False
            else:
                data['is_out_of_stock'] = True

        if data['is_out_of_stock']:
            data['available_online'] = False
            data['available_store'] = False
        else:
            available_online = re.search('this item is not available for in-store pickup', response.body_as_unicode(), re.IGNORECASE)
            available_store = re.search('your items will be available', response.body_as_unicode(), re.IGNORECASE)
            data['available_online'] = False
            data['available_store'] = False
            data['is_in_store_only'] = False
            if available_store:
                data['is_in_store_only'] = True
                data['available_online'] = False
                data['available_store'] = True
            elif available_online:
                data['available_online'] = True
                data['available_store'] = False
                data['is_in_store_only'] = False

        # currency
        currency = response.xpath(self.XPATH['product']['currency']).extract()
        _populate(data, 'currency', currency, first=True)

        # price
        price = response.xpath(self.XPATH['product']['price']).extract()
        if price:
            price = price[0].strip(currency[0])
            data['price'] = float(price)

        # size
        size = response.xpath(self.XPATH['product']['size']).extract()
        _populate(data, 'size', size)

        # color
        color = response.xpath(self.XPATH['product']['color']).extract()
        _populate(data, 'color', color)

        return data

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """

        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs
        return req.replace(meta=new_meta)

    def _parse_buyer_reviews(self, response):
        product = self.br._parse_buyer_reviews_from_filters(response)
        reqs = response.meta.get('reqs')
        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _total_matches_from_html(self, response):
        total_matches = response.xpath(self.XPATH['search']['total_matches']).extract()
        try:
            total_matches = int(re.findall(r'\d+', total_matches[0].replace(',', ''))[0])
        except Exception as e:
            self.log('Total Matches error {}'.format(traceback.format_exc(e)))
            total_matches = 0

        return total_matches

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath(self.XPATH['search']['next_page']).extract()
        if next_page:
            return next_page[0]

    def _scrape_product_links(self, response):
        for link in response.xpath(self.XPATH['search']['prod_links']).extract():
            yield link.split('?')[0].split(';')[0], SiteProductItem()
