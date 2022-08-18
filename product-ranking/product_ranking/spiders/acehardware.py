# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import urlparse
import traceback

from scrapy.log import INFO
from scrapy.http import Request
from scrapy.conf import settings

from product_ranking.items import (BuyerReviews, SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty
from product_ranking.guess_brand import guess_brand_from_first_words


class AcehardwareProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'acehardware_products'
    allowed_domains = ["www.acehardware.com", "acehardware.com"]

    SEARCH_URL = "http://www.acehardware.com/search/index.jsp?kw={search_term}"

    NEXT_PAGE_URL = "http://www.acehardware.com/search/index.jsp?page={page_num}&kw={search_term}"
    current_page = 1

    def __init__(self, *args, **kwargs):
        super(AcehardwareProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        for request in super(AcehardwareProductsSpider, self).start_requests():
            meta = request.meta.copy()
            meta['prod_count'] = 9
            request = request.replace(meta=meta)
            if self.searchterms:
                request = request.replace(callback=self.parse_redirect)
            yield request

    def parse_redirect(self, response):
        if 'Search Results' in response.body_as_unicode():
            return self.parse(response)
        else:
            prod = SiteProductItem()
            prod['url'] = response.url
            prod['search_term'] = response.meta['search_term']
            prod['total_matches'] = 1
            prod['search_redirected_to_product'] = True
            prod['ranking'] = 1
            prod['results_per_page'] = 1
            response.meta['product'] = prod
            return self.parse_product(response)

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse upc
        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc, conv=string.strip)

        # Parse reseller_id
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id, conv=string.strip)

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
        cond_set_value(product, 'price', price)

        # Parse out of stock
        is_out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        return product

    @staticmethod
    def _parse_title(response):
        title = is_empty(response.xpath('//div[contains(@id, "prodRCol")]'
                                        '/div/h2[contains(@class, "prodC1")]/text()').extract())

        return title

    @staticmethod
    def _parse_categories(response):
        category_list = []
        categories = response.xpath('//div[contains(@id, "crumbs")]//text()').extract()
        for category in categories:
            category = category.strip()
            if category and not category == '>':
                category_list.append(category)

        return category_list

    @staticmethod
    def _parse_upc(response):
        upc = re.search("upcNo=(.*?)'", response.body, re.DOTALL)
        if upc:
            upc = upc.group(1)
            return upc[-12:].zfill(12)

    @staticmethod
    def _parse_price(response):
        currency = "USD"
        price = is_empty(response.xpath('//div[@class="productPrice"]/span/text()').extract())
        if price:
            return Price(price=float(price.replace("$", '')), priceCurrency=currency)

    @staticmethod
    def _parse_brand(response):
        brand = is_empty(response.xpath('//span[@class="pr-brand"]/text()').extract())
        if not brand:
            brand = guess_brand_from_first_words(is_empty(response.xpath('//h2[@class="prodC1"]/text()').extract()))
        if brand:
            return brand

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = re.search("'vendor_sku' : '(.*?)',", response.body, re.DOTALL)
        if reseller_id:
            return reseller_id.group(1)

    @staticmethod
    def _parse_is_out_of_stock(response):
        is_out_of_stock = response.xpath('//button[@class="disable-add-to-cart"]').extract()
        return bool(is_out_of_stock)

    @staticmethod
    def _parse_image_url(response):
        image_url = is_empty(response.xpath('//div[contains(@class, "mainImageSize")]'
                                            '/img[@id="mainProdImage"]/@src').extract())
        return image_url

    def _parse_buyer_reviews(self, response):
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            rew_num = response.xpath('//p[@class="pr-snapshot-average-based-on-text"]'
                                     '/span[@class="count"]/text()').extract()
            rew_num = int(rew_num[0]) if rew_num else 0
            one_by_star = []
            two_by_star = []
            three_by_star = []
            four_by_star = []
            five_by_star = []
            rating_stars = response.xpath('//div[contains(@class, "pr-review-wrap")]'
                                          '//div[@class="pr-review-rating"]/span[contains(@class, "pr-rating")]'
                                          '/text()').extract()

            for rating in rating_stars:
                if rating == '1.0':
                    one_by_star.append(rating)
                if rating == '2.0':
                    two_by_star.append(rating)
                if rating == '3.0':
                    three_by_star.append(rating)
                if rating == '4.0':
                    four_by_star.append(rating)
                if rating == '5.0':
                    five_by_star.append(rating)

            rating_by_star = {'1': len(one_by_star), '2': len(two_by_star),
                              '3': len(three_by_star), '4': len(four_by_star),
                              '5': len(five_by_star)}

            average_rating = response.xpath('//div[contains(@class, "pr-snapshot-rating")]'
                                            '/span[contains(@class, "average")]/text()').extract()
            average_rating = average_rating[0] if average_rating else 0
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
        total_count = response.xpath('//div[contains(@class, "paginationPages")]'
                                     '/div[contains(@class, "show_products")]'
                                     '/text()').extract()
        if total_count:
            totals = re.search('of (\d+)', total_count[0].strip())
            return int(totals.group(1)) if totals else 0

    def _scrape_results_per_page(self, response):
        item_count = response.xpath('//div[contains(@class, "paginationPages")]'
                                    '/div[contains(@class, "show_products")]'
                                    '/text()').extract()
        if item_count:
            item_count = re.findall('1-(\d+) of', item_count[0].strip())
            return int(item_count[0]) if item_count else None

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//ol[contains(@id, "products")]'
                               '/li//div[@class="details"]'
                               '//a[contains(@class, "titleLink")]/@href').extract()

        if items:
            for item in items:
                link = urlparse.urljoin(response.url, item)
                res_item = SiteProductItem()
                yield link, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        prod_count = meta.get('prod_count')
        total_matches = self._scrape_total_matches(response)

        if (not total_matches) or total_matches and total_matches <= self.current_page * prod_count:
            return
        self.current_page += 1

        next_page = self.NEXT_PAGE_URL.format(page_num=self.current_page, search_term=meta.get('search_term'))
        return Request(
            next_page,
            meta=meta
        )
