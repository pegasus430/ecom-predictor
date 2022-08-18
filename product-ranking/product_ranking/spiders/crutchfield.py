# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import re
import json
from product_ranking.items import SiteProductItem, RelatedProduct, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider
from product_ranking.spiders import cond_set_value, FormatterWithDefaults, \
    FLOATING_POINT_RGEX
from scrapy.conf import settings
from scrapy import Request
from scrapy.log import DEBUG, ERROR, WARNING
import traceback


class CrutchfieldProductsSpider(BaseProductsSpider):
    name = 'crutchfield_products'
    allowed_domains = ["www.crutchfield.com", "www1.crutchfield.com"]
    SEARCH_URL = "https://www.crutchfield.com/handlers/product/search/list.ashx?" \
                 "search={search_term}&pg={page_num}&start={start_position}"
    REVIEWS_URL = "https://www.crutchfield.com/handlers/product/item/reviews.ashx?i={product_id}"

    def __init__(self, *args, **kwargs):
        super(CrutchfieldProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                page_num=1,
                start_position=0
            ),
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = \
            'product_ranking.utils.CustomClientContextFactory'

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        # Parse out of stock
        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse no longer available
        no_longer_available = self._no_longer_available(response)
        cond_set_value(product, 'no_longer_available', no_longer_available)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse reseller id
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        cond_set_value(product, 'department', categories[-1]) if categories else None

        # # Parse buyer reviews
        if reseller_id:
            new_meta = {}
            product['variants'] = []
            new_meta['product'] = product
            is_variants = response.xpath('//input/@data-cf-multiprod-url')
            if is_variants:
                setattr(response, '_{class_name}__meta'.format(class_name=type(response).__name__), new_meta)
                return self._parse_variants(response)
            else:
                return Request(self.REVIEWS_URL.format(product_id=reseller_id),
                               dont_filter=True,
                               callback=self._parse_buyer_reviews,
                               meta=new_meta)
        return product

    def _parse_variants(self, response):
        response.meta.update({'variant_links': response.xpath('//input/@data-cf-multiprod-url').extract()})
        return self._extract_variant(response)

    def _extract_variant(self, response):
        sku = self._parse_sku(response)
        price = self._get_plain_price(response)
        oos = self._parse_out_of_stock(response)
        label = self._get_variant_label(response, sku)
        response.meta['product']['variants'].append({
            label: {
                'price': price,
                'properties': {
                    'sku': sku,
                    'in_stock': not (oos)
                }
            }})
        if response.meta['variant_links']:
            link = response.meta['variant_links'].pop(0)
            return Request(link, dont_filter=True, callback=self._extract_variant, meta=response.meta)
        else:
            response.meta['product']['variants'].pop(0)
            reseller_id = response.meta['product']['sku']
            return Request(self.REVIEWS_URL.format(product_id=reseller_id),
                           dont_filter=True,
                           callback=self._parse_buyer_reviews,
                           meta=response.meta)

    def _get_plain_price(self, response):
        try:
            price = response.xpath('//meta[@itemprop="price"]/@content').extract()
            if price:
                return float(price[0])
        except:
            self.log("Failed to parse variant price", WARNING)

    @staticmethod
    def _get_variant_label(response, sku):
        label = response.xpath('//label[@for="{}"]/span/text()'.format(sku))
        if not label:
            label = response.xpath('//label[@for="{}"]/text()'.format(sku))
        return label[0].extract().strip() if label else 'option'

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id_regex = r"(?<=p_)[^/]+"
        reseller_id = re.findall(reseller_id_regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        return reseller_id

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath(
            './/*[@itemprop="brand"]/meta[@itemprop="name"]/@content').extract()
        return brand[0] if brand else None

    @staticmethod
    def _parse_title(response):
        title = response.xpath(
            '//meta[@name="title"]/@content').extract()
        return title[0] if title else None

    @staticmethod
    def _no_longer_available(response):
        return bool(response.xpath('//strong[text()="This item is no longer available."]'))

    @staticmethod
    def _parse_out_of_stock(response):
        out_of_stock = response.xpath('//div[contains(@class, "prodBuyBox")]//span[contains(@class, "stock-out")]')
        return bool(out_of_stock)

    def _parse_price(self, response):
        price = response.xpath('//meta[@itemprop="price"]/@content').re(FLOATING_POINT_RGEX)
        currency = response.xpath('//meta[@itemprop="priceCurrency"]/@content').extract()
        currency = currency[0] if currency else 'USD'
        if price:
            return Price(price=float(price[0]), priceCurrency=currency)

    def _parse_description(self, response):
        description = response.xpath(
            '//p[@class="expertTagLine hidden-xxs"]/text()').extract()
        if not description:
            description = response.xpath("//div[contains(@class, 'overviewCopy')]//p/text()").extract()
        return self._clean_text(description[0]) if description else None

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath(
            "//meta[@property='og:image']/@content").extract()
        image_url = image_url[0].replace("?$preview$", "") if image_url else None
        return image_url

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath(
            "//span[@itemprop='sku']/text()").extract()
        sku = sku[0] if sku else None
        return sku

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath(
            "//div[contains(@class, 'hidden-xs')]/div[@class='crumb']//span[@itemprop='title']/text()").extract()
        if 'Home' in categories:
            categories.remove('Home')
        return categories

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            reviews_json = json.loads(response.body)
            reviews_json = reviews_json.get('RatingList')
            rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
            for item in reviews_json:
                rating_by_star[str(item.get('Rating'))] = item.get('Count')
            num_of_reviews = sum([rating_by_star[x] for x in rating_by_star])
            average_rating = round(float(sum([rating_by_star[x] * int(x) for x in rating_by_star])) / num_of_reviews, 2)
            buyer_reviews = {
                'num_of_reviews': num_of_reviews,
                'average_rating': average_rating,
                'rating_by_star': rating_by_star}
        except:
            self.log("Failed to load reviews from json file or there are no reviews for the product.", DEBUG)
            buyer_reviews = ZERO_REVIEWS_VALUE
        product['buyer_reviews'] = buyer_reviews
        return product

    def _scrape_total_matches(self, response):
        try:
            total = json.loads(response.body)
            return int(total.get('Total'))
        except:
            self.log("Failed to parse total matches count", WARNING)

    def _scrape_product_links(self, response):
        try:
            response = json.loads(response.body)
            products = response.get('Products')
            for product in products:
                link = product.get('computed', {}).get('Url')
                if link:
                    yield link, SiteProductItem()
        except:
            self.log("Failed to parse product links", WARNING)

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page')
        if not current_page:
            current_page = 1
        total = self._scrape_total_matches(response)
        start_position = current_page * 20
        if total > start_position:
            search_term = response.meta['search_term']
            current_page += 1
            response.meta['current_page'] = current_page
            return Request(self.SEARCH_URL.format(search_term=search_term,
                                                  page_num=current_page,
                                                  start_position=start_position),
                           meta=response.meta)

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()
