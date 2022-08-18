# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import urllib
import urlparse

import traceback
import json

from scrapy import Request
from scrapy.log import INFO, WARNING
from scrapy.conf import settings
from product_ranking.guess_brand import guess_brand_from_first_words

from product_ranking.items import (BuyerReviews, SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty


class BhphotovideoProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'bhphotovideo_products'
    allowed_domains = ["www.bhphotovideo.com", "bhpphotovideo.com"]

    SEARCH_URL = "https://www.bhphotovideo.com/c/search?Ntt={search_term}&N=0&InitialSearch=yes&sts=ma&Top+Nav-Search="

    REVIEW_URL = "https://www.bhphotovideo.com/bnh/controller/home?A=GetReviews&Q=json&O=&" \
                 "sku={sku}&" \
                 "pageSize=100&" \
                 "pageNum=0&" \
                 "currReviews={review_num}"

    def __init__(self, *args, **kwargs):
        super(BhphotovideoProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        settings.overrides['USE_PROXIES'] = True

    def start_requests(self):
        """Generate Requests from the SEARCH_URL and the search terms."""
        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                ),
                dont_filter=True,
                meta={'search_term': st, 'remaining': self.quantity},
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.product_url,
                          self._parse_single_product,
                          dont_filter=True,
                          meta={'product': prod})

        if self.products_url:
            urls = self.products_url.split('||||')
            for url in urls:
                prod = SiteProductItem()
                prod['url'] = url
                prod['search_term'] = ''
                yield Request(url,
                              self._parse_single_product,
                              dont_filter=True,
                              meta={'product': prod})

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # # Set locale
        # product['locale'] = 'en_CA'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        brand = self._parse_brand(response)
        if not brand:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku, conv=string.strip)

        # Parse reseller_id
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        # Parse is_out_of_stock
        out_of_stock = self._parse_out_of_stock(response)
        product['is_out_of_stock'] = out_of_stock

        # Review number
        review_num = is_empty(response.xpath('//span[@itemprop="reviewCount"]/text()').extract())

        # Parse buyer reviews
        if review_num:
            return Request(self.REVIEW_URL.format(sku=sku, review_num=review_num),
                           dont_filter=True,
                           meta=response.meta,
                           callback=self._parse_buyer_reviews)
        return product

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//span[@itemprop="brand"]/text()').extract()
        return brand[0] if brand else None

    @staticmethod
    def _parse_title(response):
        title = is_empty(response.xpath('//span[@itemprop="name"]/text()').extract())
        return title.strip()

    @staticmethod
    def _parse_sku(response):
        sku = is_empty(response.xpath('//input[@name="sku"]/@value').extract())
        return sku

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = is_empty(response.xpath('//meta[@itemprop="productID"]/@content').extract())
        if reseller_id:
            return reseller_id.split(':')[-1]

    @staticmethod
    def _parse_categories(response):
        categories_sel = response.xpath('//ul[@id="breadcrumbs"]'
                                        '/li/a/text()').extract()
        categories = [i.strip() for i in categories_sel]
        return categories

    def _parse_price(self, response):
        currency = "USD"
        price = re.search('mainPrice = "(.*?)"', response.body, re.DOTALL)
        if price:
            return Price(price=float(price.group(1)), priceCurrency=currency)

    @staticmethod
    def _parse_image_url(response):
        image_url = is_empty(response.xpath('//img[@id="mainImage"]/@src').extract())
        return image_url

    @staticmethod
    def _parse_description(response):
        description = response.xpath('//ul[@data-selenium="highlightList"]/li/text()').extract()
        return " ".join(description)

    @staticmethod
    def _parse_out_of_stock(response):
        availability = is_empty(response.xpath('//div[@data-selenium="salesComments"]/span/text()').extract())
        return not (availability == "In Stock")

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']
        zero_reviews_value = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            data = json.loads(response.body_as_unicode())

            data = data.get("snapshot")
            review_count = data.get('num_reviews')

            rating_by_star = data.get("rating_histogram")

            average_rating = data.get("average_rating", 0)

            buyer_reviews = {
                'num_of_reviews': review_count,
                'average_rating': round(float(average_rating), 1) if average_rating else 0,
                'rating_by_star': rating_by_star
            }
            product['buyer_reviews'] = buyer_reviews

        except:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()), WARNING)
            return BuyerReviews(**zero_reviews_value)

        return product

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        totals = response.xpath('//span[@class="fs16 bold"]/text()').re('\d+')
        return int(totals[-1]) if totals else None

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//div[@data-selenium="itemDetail"]//a[@name="image"]/@href').extract()

        if items:
            for item in items:
                res_item = SiteProductItem()
                yield item, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath('//a[@data-selenium="pn-next"]/@href').extract()
        if next_page:
            return urlparse.urljoin(response.url, next_page[0])
