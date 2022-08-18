# -*- coding: utf-8 -*-#
from __future__ import unicode_literals

import re
import json
import string
import traceback

from scrapy.http import Request
from scrapy.log import ERROR, INFO, WARNING

from product_ranking.items import SiteProductItem, RelatedProduct, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from spiders_shared_code.debenhams_variants import DebenhamsVariants


is_empty = lambda x, y=None: x[0] if x else y


class DebenhamsProductSpider(BaseProductsSpider):

    name = 'debenhams_products'
    allowed_domains = ["debenhams.com"]

    SEARCH_URL = 'http://www.debenhams.com/search/{search_term}'

    items_per_page = 60

    BUYER_REVIEWS_URL = 'http://debenhams.ugc.bazaarvoice.com/' \
                        '9364redes-en_gb/{prod_id}/reviews.djs?format=embeddedhtml'

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)
        self.dv = DebenhamsVariants()

        super(DebenhamsProductSpider, self).__init__(*args, **kwargs)

    def parse_product(self, response):
        reqs = []
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
        price, currency = self._parse_price(response)
        price = Price(price=float(price), priceCurrency=currency) if price else None
        cond_set_value(product, 'price', price)

        # Parse special pricing
        special_pricing = self._parse_special_pricing(response)
        cond_set_value(product, 'special_pricing', special_pricing, conv=bool)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        # Parse stock status
        is_out_of_stock = self._parse_stock_status(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse upc
        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc)

        # Parse Was Now
        was_now = self._parse_was_now(response)
        cond_set_value(product, 'was_now', was_now)

        # Parse Save Amount
        save_amount = self._parse_save_amount(response)
        cond_set_value(product, 'save_amount', save_amount)

        if any([was_now, save_amount]):
            product['promotions'] = True
        else:
            product['promotions'] = False

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Parse resellerId
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse variants
        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        # Parse buyer reviews
        if reseller_id:
            reqs.append(
                Request(
                    url=self.BUYER_REVIEWS_URL.format(prod_id=reseller_id),
                    dont_filter=True,
                    callback=self.br.parse_buyer_reviews
                )
            )

        # Parse related products
        related_products = self._parse_related_products(response)
        cond_set_value(product, 'related_products', related_products)

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_title(self, response):
        title = is_empty(
            response.xpath('//meta[@property="og:title"]/@content').extract()
        )

        return title

    def _parse_brand(self, response):
        brand = is_empty(
            response.xpath('//img[@class="brand"]/@alt').extract()
        )

        if not brand:
            brand = is_empty(response.xpath(
                '//meta[@property="brand"]/@content'
            ).extract())

        return brand

    def _parse_department(self, response):
        # field is not present in the new design
        department = is_empty(
            response.xpath('//meta[@property="department"]/@content').extract()
        )

        return department

    def _parse_categories(self, response):
        categories = []
        categories_sel = response.xpath(
                '//div[@class="breadcrumb"]/ol/li//text()').extract()
        for cat in categories_sel:
            categories.append(cat.strip())
        return categories

    def _parse_price(self, response):
        price_data = response.xpath('//script[@type="application/ld+json"]/text()').extract()
        try:
            price = re.search(r'"price": "(\d+[\.]\d*)"', price_data[0])
            price_currency = re.search(r'"priceCurrency": "(.*?)"', price_data[0])
            return price.group(1), price_currency.group(1)
        except:
            self.log('Error Parsing Price: {}'.format(traceback.format_exc()), WARNING)

    def _parse_special_pricing(self, response):
        special_pricing = is_empty(
            response.xpath('//li[@class="first-child attr-price-was"]/span[2]').extract(),
            False
        )

        return special_pricing

    def _parse_was_now(self, response):
        was_now = None
        current_price = self._parse_price(response)
        past_price = response.xpath('//div[@class="product-options-container"]'
                                    '//div[@class="previous-prices"]').extract()
        if past_price:
            past_price = re.findall(r'\d+\.*\d*', past_price[0])
            if past_price and current_price:
                was_now = ', '.join([current_price[0], past_price[0]])
        return was_now

    def _parse_save_amount(self, response):
        save_amount = response.xpath('//div[@class="product-options-container"]'
                                     '//div[@class="savingamount"]').extract()
        if save_amount:
            save_amount = re.findall(r'\d+\.*\d*', save_amount[0])
            return save_amount[0] if save_amount else None

    def _parse_image_url(self, response):
        image_url = is_empty(
            response.xpath('//meta[@property="og:image"]/@content').extract()
        )

        return image_url

    def _parse_description(self, response):
        description = is_empty(
            response.xpath('//h3[@class="description"]/text()').extract()
        )

        if not description:
            description = is_empty(response.xpath(
                '//meta[@property="description"]/@content'
            ).extract())

        return description

    def _parse_stock_status(self, response):
        stock_status = is_empty(
            response.xpath('//meta[@name="twitter:data2"]/@content').extract()
        )

        if stock_status and 'in stock' in stock_status.lower():
            stock_status = False
        else:
            stock_status = True

        return stock_status

    def _parse_upc(self, response):
        upc = is_empty(
            response.xpath('//span[@class="product-code"]/text()').extract()
        )

        try:
            upc = re.search(r'productId[\"\']\s?\:\s?[\'\"](\d+)',
                                   response.body).group(1)
        except Exception as e:
            self.log('Can\'t find product id. ERROR: %s.' % str(e), ERROR)

        if upc:
            return upc

        return None

    def _parse_sku(self, response):
        sku = response.xpath("//meta[@property='item_number']/@content").extract()
        return sku[0] if sku else None

    def _parse_reseller_id(self, response):
        reseller_id = response.xpath("//meta[@property='product_number']/@content").extract()
        return reseller_id[0] if reseller_id else None

    def _parse_variants(self, response):
        variants = response.xpath('//script[@id="productDataAsJSON"]/text()').extract()
        try:
            variants = json.loads(variants[0])
            variants = variants.get('product', {}).get('items', [])
            self.dv.setupSC(variants)
            return self.dv._variants()
        except:
            self.log('Error Parsing Variant:{}'.format(traceback.format_exc()), WARNING)

    def _parse_related_products(self, response):
        related_products = []
        title = response.xpath('//div[@class="product-cross-sells '
                               'tab-container"]//ul[@class="jcarousel-skin-1"]'
                               '/li/div[1]/h2/a/text()').extract()
        url = response.xpath('//div[@class="product-cross-sells '
                             'tab-container"]//ul[@class="jcarousel-skin-1"]'
                             '/li/div[1]/h2/a/@href').extract()

        if title and url:
            for index, title in enumerate(title):
                related_products.append(
                    RelatedProduct(
                        url=url[index],
                        title=title
                    )
                )
            return related_products

        if related_products:
            return related_products
        else:
            return None

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """

        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs
        return req.replace(meta=new_meta)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        total_matches = is_empty(
            response.xpath(
                '//span[@class="products_count"]/text()'
            ).re('(\d+)'), 0
        )

        return int(total_matches)

    def _scrape_results_per_page(self, response):
        return self.items_per_page

    def _scrape_product_links(self, response):
        links = response.xpath('//div[contains(@class, "item_container")]//'
                               'input/@value').extract()
        if links:
            for link in links:
                yield link, SiteProductItem()
        else:
            self.log("Found no product links in {url}".format(
                url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        url = response.xpath('//div[@class="product_nav"]//'
                             'a[contains(text(), "Next")]/@href').extract()
        if url:
            return url[0]
        else:
            self.log("Found no 'next page' links", WARNING)
            return None
