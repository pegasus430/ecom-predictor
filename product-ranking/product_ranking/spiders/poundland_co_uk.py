# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import json
import re
import string
import traceback

from scrapy import Request
from scrapy.conf import settings
from scrapy.selector import Selector

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider, FormatterWithDefaults,
                                     cond_set_value)
from product_ranking.utils import extract_first, is_empty
from product_ranking.validation import BaseValidator


class PoundlandCoUkProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'poundland_co_uk_products'
    allowed_domains = ["poundland.co.uk"]

    CATEGORY_URL = "http://www.poundland.co.uk/ajax-breadcrumbs/ajax/"
    REVIEW_URL = "http://www.poundland.co.uk/ajax-rating/add/?product_id={product_id}"

    SEARCH_URL = "http://www.poundland.co.uk/ampersand-ajaxproductloader/index/index/?" \
                 "q={search_term}&page={page_num}"

    def __init__(self, *args, **kwargs):
        super(PoundlandCoUkProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(page_num=1),
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        settings.overrides['USE_PROXIES'] = True

        self.current_page = 1
        self.cid = None
        self.default_cid = None
        self.total_match = None

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        if 'product-view' not in response.body_as_unicode():
            return

        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse category_id
        category_ids = re.search('product_category_ids: {(.*?)}', response.body)
        default_id = re.search('default_category_id: (.*?),', response.body)
        default_id = default_id.group(1).replace("'", "") if default_id else None
        self.default_cid = default_id

        if category_ids:
            category_ids = category_ids.group(1).split(',')
            category_ajax_id = category_ids[0].split(':')[0].replace('"', '')
            self.cid = category_ajax_id

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        # Parse brand
        brand = self._parse_brand(response, title, description)
        cond_set_value(product, 'brand', brand)

        # Parse Reseller Id
        reseller_id = response.url.split('/')
        if len(reseller_id) > 1:
            reseller_id = reseller_id[-1].replace('-', '')
            cond_set_value(product, 'reseller_id', reseller_id)

        # Product Id
        product_id = response.xpath('//input[@name="product"]/@value').extract()

        # Parse buyer reviews
        if product_id:
            product_id = product_id[0]
            return Request(self.REVIEW_URL.format(product_id=product_id),
                           dont_filter=True,
                           meta=response.meta,
                           callback=self._parse_buyer_reviews)

        return product

    @staticmethod
    def _parse_title(response):
        title = is_empty(response.xpath('//div[contains(@class, "product-name")]'
                                        '/h1/text()').extract())

        return title

    def _parse_categories(self, response):
        category_list = []
        product = response.meta['product']
        try:
            category_data = json.loads(response.body_as_unicode())

            if self.cid in category_data:
                category_list.append(category_data[self.cid]['name'])

                if category_data[self.cid]['parent_id']:
                    category_parent_id = category_data[self.cid]['parent_id']
                    category_list.append(category_data[str(category_parent_id)]['name'])

                    if category_data[str(category_parent_id)]['parent_id']:
                        category_sub_parent_id = category_data[str(category_parent_id)]['parent_id']
                        category_list.append(category_data[str(category_sub_parent_id)]['name'])

                        if category_data[str(category_sub_parent_id)]['parent_id']:
                            category_main_parent_id = category_data[str(category_sub_parent_id)]['parent_id']
                            category_list.append(category_data[str(category_main_parent_id)]['name'])
                category_list = list(reversed(category_list))

            else:
                category_list.append(category_data[self.default_cid]['name'])

            product['categories'] = category_list
            product['department'] = category_list[-1]

        except:
            self.log("Found no categories: {}".format(traceback.format_exc()))
            product['categories'] = None
            product['department'] = None
        finally:
            return product

    @staticmethod
    def _parse_price(response):
        currency = "GBP"
        price = response.xpath('//div[contains(@class, "product-image")]/img/@alt').extract()
        if price:
            price = price[0]
            base_price = re.search('\xa3(\d+\.?\d+)', price)
            special_price = re.search('(\d+\.?\d+)', price)
            if base_price:
                price = base_price.group(1)
            elif special_price:
                price = special_price.group()
            return Price(price=float(price.replace(",", "")), priceCurrency=currency)

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath('//meta[@property="og:image"]/@content').extract()
        if image_url:
            image_url = image_url[0].replace('265x', '370x')
            return image_url

    @staticmethod
    def _parse_description(response):
        description = response.xpath('//meta[@name="description"]/@content').extract()
        description = "".join(description)
        return description

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {}
        }
        try:
            data = json.loads(response.body_as_unicode())

            rew_num = int(data['rating_count'])

            percent_review = float(data['rating_percentage'])
            average_rating = str(percent_review / 100 * 5)

            buyer_reviews = {
                'num_of_reviews': rew_num,
                'average_rating': round(float(average_rating), 1),
                'rating_by_star': {}
            }
            product['buyer_reviews'] = buyer_reviews

            if self.cid:
                return Request(self.CATEGORY_URL,
                               dont_filter=True,
                               meta=response.meta,
                               callback=self._parse_categories)

            return product
        except:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()))
            return BuyerReviews(**ZERO_REVIEWS_VALUE)

    @staticmethod
    def _parse_brand(response, title, description):
        brand = extract_first(response.xpath('//div[contains(@class, "product-brand")]/img/@alt'))
        return brand or guess_brand_from_first_words(title) or guess_brand_from_first_words(description)

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            totals = data['total']
        except:
            totals = 0
            self.log("Found no total matches. {}".format(traceback.format_exc()))
        return totals

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        try:
            data = json.loads(response.body_as_unicode())
            content = data['content']

            items = Selector(text=content).xpath('//ul[contains(@class, "products-grid")]'
                                                 '/li/a[contains(@class, "product-image")]/@href').extract()
            if items:
                for item in items:
                    res_item = SiteProductItem()
                    yield item, res_item
        except:
            self.log("Found no product links: {}".format(traceback.format_exc()))

    def _scrape_next_results_page_link(self, response):
        try:
            next_page_load = json.loads(response.body_as_unicode())['nextPageToLoad']
            self.current_page += 1

            if next_page_load != 0:
                next_page = self.SEARCH_URL.format(page_num=self.current_page,
                                                   search_term=response.meta.get('search_term'))
                return next_page
        except:
            self.log("Found no next link: {}".format(traceback.format_exc()))
