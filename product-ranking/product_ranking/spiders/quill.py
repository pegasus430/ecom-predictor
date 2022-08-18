# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import urlparse
import traceback
import json
import time

from scrapy.log import INFO, WARNING
from scrapy.conf import settings
from scrapy.http import Request

from product_ranking.items import (BuyerReviews, SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults, FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty


class QuillProductsSpider(BaseValidator, BaseProductsSpider):

    name = 'quill_products'
    allowed_domains = ["www.quill.com", "quill.com"]

    SEARCH_URL = "https://www.quill.com/search?x=0&y=0&keywords={search_term}&ajx=1"

    NEXT_URL = "https://www.quill.com/SearchEngine/GetSearchResults?keywords={search_term}&" \
                    "filter=0&sortOption=BestMatch&browseType=&finderId=0&_={begin_index}"
    current_page = 1

    def __init__(self, *args, **kwargs):
        super(QuillProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse Brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse buyer reviews
        buyer_reviews = self._parse_buyer_reviews(response)
        cond_set_value(product, 'buyer_reviews', buyer_reviews)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse price
        price = self._parse_price(response)
        if price:
            cond_set_value(product, 'price', Price(price=float(price), priceCurrency='USD'))

        was_now = self._parse_was_now(response)
        cond_set_value(product, 'was_now', was_now)

        save_amount = self._parse_save_amount(response)
        cond_set_value(product, 'save_amount', save_amount)

        # Parse price_per_volume
        price_per_volume = self._parse_price_per_volume(response)
        cond_set_value(product, 'price_per_volume', price_per_volume)

        # Parse price_volume_measure
        price_volume_measure = self._parse_price_volume_measure(response)
        cond_set_value(product, 'volume_measure', price_volume_measure)

        cond_set_value(product, 'promotions', any([
            save_amount,
            was_now,
            price_per_volume,
            price_volume_measure
        ]))

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', 'https:' + image_url if image_url else image_url, conv=string.strip)

        # Parse model
        model = self._parse_model(response)
        cond_set_value(product, 'model', model, conv=string.strip)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        cond_set_value(product, 'reseller_id', sku)

        is_out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        return product

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//div[@class="formLabel SL_m" and contains(span/text(), "Brand:")]/text()').extract()
        return brand[0] if brand else None

    @staticmethod
    def _parse_title(response):
        title = is_empty(response.xpath('//h1[@class="skuName"]/text()').extract())
        return title

    @staticmethod
    def _parse_categories(response):
        category_list = []
        categories = response.xpath('//div[@id="skuBreadCrumbs"]//li/a/span/text()').extract()
        for category in categories:
            category = category.strip()
            if category and not category == '>':
                category_list.append(category)

        return category_list

    @staticmethod
    def _parse_price(response):
        price = is_empty(response.xpath('//input[@id="QuantityInput"]/@data-price').re(FLOATING_POINT_RGEX))
        return format(float(price.replace(',', '')), '.2f') if price else None

    @staticmethod
    def _parse_price_per_volume(response):
        volume = is_empty(response.xpath('//input[@id="QuantityInput"]'
                                         '/@data-basepricebreak').re('=(\d{1,3}[,\d{3}]*\.?\d*)/'))
        return format(float(volume.replace(',', '')), '.2f') if volume else None

    @staticmethod
    def _parse_price_volume_measure(response):
        measure = is_empty(response.xpath('//input[@id="QuantityInput"]/@data-basepricebreak').re('/(.*?),'))
        return measure

    def _parse_was_now(self, response):
        current_price = self._parse_price(response)
        old_price = is_empty(response.xpath('//input[@id="QuantityInput"]/@data-wasprice').re(FLOATING_POINT_RGEX))
        if old_price and current_price:
            old_price = format(float(old_price.replace(',', '')), '.2f')
            return ','.join([current_price, old_price])

    def _parse_save_amount(self, response):
        current_price = self._parse_price(response)
        old_price = is_empty(response.xpath('//input[@id="QuantityInput"]/@data-wasprice').re(FLOATING_POINT_RGEX))
        if old_price and current_price:
            return format(float(old_price) - float(current_price), '.2f')

    @staticmethod
    def _parse_image_url(response):
        image_url = is_empty(response.xpath('//img[@id="SkuPageMainImg"]/@src').extract())
        return image_url if image_url else None

    def _parse_model(self, response):
        try:
            data = json.loads(response.xpath('//script[@type="application/ld+json"]/text()').extract()[0])
            return data.get('model', '').replace('Model #: ', '')
        except:
            self.log('Error parsing model json: {}'.format(traceback.format_exc()), WARNING)

    def _parse_sku(self, response):
        sku = response.xpath('//div[@class="skuProductNames"]//div[@class="formLabel"]/text()').extract()
        return sku[0].strip() if sku else None

    @staticmethod
    def _parse_is_out_of_stock(response):
        out_of_stock = re.search(r'stock":{"OOS":"(.*?)"', response.body, re.DOTALL)
        if out_of_stock:
            return out_of_stock.group(1) != 'false'
        return False

    def _parse_buyer_reviews(self, response):
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            rew_num = response.xpath('//span[@class="yotpo-sum-reviews"]/span/text()').extract()
            rew_num = re.search('(\d+)', rew_num[0])
            if rew_num:
                rew_num = int(rew_num.group(1))

            stars = response.xpath('//div[@class="yotpo-distibutions-sum-reviews"]/span/text()').extract()
            rating_stars = []
            for star in stars:
                star = re.search('(\d+)', star)
                if star:
                    rating_stars.append(star.group(1))

            rating_by_star = {'1': int(rating_stars[4]), '2': int(rating_stars[3]),
                              '3': int(rating_stars[2]), '4': int(rating_stars[1]),
                              '5': int(rating_stars[0])}

            average_rating = response.xpath('//span[@class="yotpo-star-digits"]/text()').extract()
            average_rating = average_rating[0].strip() if average_rating else 0
            buyer_reviews = {
                'num_of_reviews': rew_num,
                'average_rating': round(float(average_rating), 1),
                'rating_by_star': rating_by_star
            }
        except Exception as e:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()))
            return BuyerReviews(**ZERO_REVIEWS_VALUE)
        else:
            return BuyerReviews(**buyer_reviews)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        total_count = response.xpath('//span[@id="SearchCount"]/text()').extract()
        if total_count:
            totals = re.search('(\d+)', total_count[0])
            return int(totals.group(1)) if totals else None

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//div[@id="SKUDetailsDiv"]//h3/a/@href').extract()
        items_sec = response.xpath('//div[@id="SKUDetailsDiv"]//h3/span/@data-url').extract()

        if items:
            for item in items:
                link = urlparse.urljoin(response.url, item)
                res_item = SiteProductItem()
                yield link, res_item
        elif items_sec:
            for item in items_sec:
                link = urlparse.urljoin(response.url, item)
                res_item = SiteProductItem()
                yield link, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        begin_index = response.meta.get('begin_index')
        current_page = response.meta.get('current_page')
        total_matches = response.meta.get('total_matches', 0)

        if not begin_index:
            begin_index = int(round(time.time() * 1000))
        if not current_page:
            current_page = 0
        if current_page * 24 > total_matches:
            return
        current_page += 1
        next_page = begin_index + current_page
        st = response.meta['search_term']
        url = self.NEXT_URL.format(begin_index=next_page, search_term=st)
        return Request(
            url,
            meta={
                'search_term': st,
                'remaining': self.quantity,
                'current_page': current_page,
                'begin_index': begin_index
                }, )

    def _get_products(self, response):
        for req in super(QuillProductsSpider, self)._get_products(response):
            yield req.replace(dont_filter=True)
