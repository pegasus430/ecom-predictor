# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import json
import traceback

from scrapy.log import INFO, DEBUG
from scrapy.conf import settings
from scrapy import Request
from lxml import html

from product_ranking.items import (BuyerReviews, SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty
from product_ranking.settings import ZERO_REVIEWS_VALUE

class BuybuybabyProductsSpider(BaseValidator, BaseProductsSpider):

    name = 'buybuybaby_products'
    allowed_domains = ["buybuybaby.com"]

    REVIEW_URL = "https://buybuybaby.ugc.bazaarvoice.com/8658-en_us/{prod_id}/reviews.djs?format=embeddedhtml"

    SEARCH_URL = "https://www.buybuybaby.com/api/apollo/collections/bedbath/query-profiles/v1/select?wt=json&" \
                 "q={search_term}&rows=48&start={start_num}&view=grid3&site=BuyBuyBaby"

    def __init__(self, *args, **kwargs):
        formatter = FormatterWithDefaults(start_num=0)
        super(BuybuybabyProductsSpider, self).__init__(formatter, site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse promotions
        promotions = self._parse_promotions(response)
        cond_set_value(product, 'promotions', promotions)

        # Parse out of stock
        cond_set_value(product, 'is_out_of_stock', False)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Parse buyer reviews
        prod_id = re.search("product_id = '(.*?)'", response.body, re.DOTALL)
        if prod_id:
            return Request(self.REVIEW_URL.format(prod_id=prod_id.group(1)), dont_filter=True,
                           meta=response.meta, callback=self._parse_buyer_reviews)

        return product

    @staticmethod
    def _parse_brand(response):
        brand = re.search('brand_name":"(.*?)"', response.body, re.DOTALL)
        if brand:
            return brand.group(1)

    @staticmethod
    def _parse_title(response):
        title = is_empty(response.xpath('//h1[@id="productTitle"]/text()').extract())

        return title

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//div[contains(@class, "breadcrumbs")]'
                                    '/div[contains(@class, "alpha")]/a/text()').extract()
        category_list = [cat.strip() for cat in categories]

        return category_list if category_list else None

    def _parse_price(self, response):                           
        currency = "USD"
        price = is_empty(response.xpath('//span[@itemprop="price"]/text()').extract())
        try:
            price = float(price.replace(',', ''))
            return Price(price=price, priceCurrency=currency)
        except:
            self.log('Error while parsing price {}'.format(traceback.format_exc()), DEBUG)

    def _parse_promotions(self, response):
        promotions = response.xpath('//div[@class="wasPrice"]')
        return bool(promotions)

    @staticmethod
    def _parse_image_url(response):
        image_url = is_empty(response.xpath('//img[@id="mainProductImg"]/@src').extract())
        return image_url.replace('//', 'http://')

    @staticmethod
    def _parse_description(response):
        description = response.xpath('//div[@id="productInfoWrapper"]//text()').extract()
        return ''.join(description) if description else None

    @staticmethod
    def _parse_sku(response):
        sku = is_empty(response.xpath('//input[@name="skuId"]/@value').extract())
        return sku

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']

        content = re.search(
            'BVRRRatingSummarySourceID":"(.+?)\},', response.body_as_unicode()
        )
        try:
            content = content.group(1).replace('\\"', '"').replace("\\/", "/")
            review_html = html.fromstring(content)

            arr = review_html.xpath(
                '//div[contains(@class,"BVRRQuickTakeSection")]'
                '//div[contains(@class,"BVRRRatingOverall")]'
                '//img[contains(@class,"BVImgOrSprite")]/@title'
            )

            if len(arr) > 0:
                average_rating = float(arr[0].strip().split(" ")[0])
            else:
                average_rating = 0.0

            num_of_reviews = review_html.xpath('//meta[@itemprop="reviewCount"]/@content')
            review_list = review_html.xpath('//div[@class="BVRRHistogramContent"]'
                                            '/div[contains(@class, "BVRRHistogramBarRow")]'
                                            '/span[@class="BVRRHistAbsLabel"]/text()')
            if review_list:
                review_list = review_list[:5]

            rating_by_star = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for i, value in enumerate(review_list):
                rating_by_star[5-i] = value
            if average_rating and num_of_reviews:
                    buyer_reviews = {
                        'num_of_reviews': int(num_of_reviews[0]),
                        'average_rating': float(average_rating),
                        'rating_by_star': rating_by_star
                    }
                    product["buyer_reviews"] = buyer_reviews
            else:
                product["buyer_reviews"] = ZERO_REVIEWS_VALUE
        except:
            self.log('Error while parsing review {}'.format(traceback.format_exc()), DEBUG)

        return product

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body)
            total_matches = data.get('response').get('numFound')
        except Exception as e:
            self.log("Exception looking for total_matches {}".format(e), DEBUG)
            total_matches = 0

        return total_matches

    def _scrape_product_links(self, response):
        url_head = 'https://buybuybaby.com/store'
        try:
            data = json.loads(response.body)
            links = data.get('response').get('docs')
            for link in links:
                res_item = SiteProductItem()
                url = url_head + link.get('SEO_URL')
                yield url, res_item
        except:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        st = response.meta['search_term']
        current_page = response.meta.get('current_page', 0)
        if current_page * 48 > self._scrape_total_matches(response):
            return
        next_page = current_page + 1
        url = self.SEARCH_URL.format(start_num=next_page * 48, search_term=st)
        return Request(
            url,
            meta={
                'search_term': st,
                'remaining': self.quantity,
                'current_page': next_page}, )