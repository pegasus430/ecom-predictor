# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import urlparse
import traceback
import math

from lxml import html
from scrapy import Request
from scrapy.log import WARNING, DEBUG, ERROR
from scrapy.conf import settings
from product_ranking.utils import _init_chromium

from product_ranking.items import (BuyerReviews, SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.settings import ZERO_REVIEWS_VALUE

from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class HebProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'heb_products'
    allowed_domains = ["heb.com"]

    SEARCH_URL = "https://www.heb.com/search/product-results?Ntt={search_term}&q={search_term}"

    REVIEW_URL = 'https://heb.ugc.bazaarvoice.com/9846products/{}/reviews.djs?format=embeddedhtml'

    NEXT_URL = "https://www.heb.com/search/product-results?No={offset}" \
               "&Nrpp=32&Ntt={search_term}&prodFilter=none&q={search_term}"

    results_per_page = 32

    def __init__(self, *args, **kwargs):
        super(HebProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        for request in super(HebProductsSpider, self).start_requests():
            if not self.product_url:
                request = request.replace(callback=self._parse_help)
            yield request

    def _parse_help(self, response):
        driver = None
        try:
            driver = _init_chromium()
        except:
            self.log("Could not get driver".format(traceback.format_exc()))

        if driver:
            try:
                driver.get(response.url)
                ignored_exceptions = (NoSuchElementException, StaleElementReferenceException,)
                WebDriverWait(driver, 15, ignored_exceptions=ignored_exceptions).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "search-result"))
                )
                product_data = driver.find_elements_by_xpath("//div[contains(@class, 'search-result')]")

                if not product_data:
                    raise

                response.meta['product_data'] = product_data[0]
                return self.parse(response)
            except:
                self.log('Found no product links: {}'.format(traceback.format_exc()))

            if 'driver' in locals():
                driver.quit()

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_CA'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        out_of_stock = self._parse_out_of_stock(response)
        product['is_out_of_stock'] = out_of_stock

        # Parse brand
        brand = guess_brand_from_first_words(product.get('title', ''))
        cond_set_value(product, 'brand', brand)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku, conv=string.strip)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse buyer reviews
        try:
            review_count = int(response.xpath('//input[@id="reviewCount"]/@value').extract()[0])
            average_rating = float(response.xpath('//meta[@itemprop="ratingValue"]/@content').extract()[0])

            product_id = response.xpath("//input[@id='productId']/@value").extract()[0]
            response.meta['product'] = product
            response.meta['product_id'] = product_id
            meta = response.meta
            meta['avg_rating'] = average_rating
            meta['review_count'] = review_count

            return Request(
                url=self.REVIEW_URL.format(product_id),
                dont_filter=True,
                callback=self._parse_buyer_reviews,
                meta=meta
            )
        except:
            self.log("Review Error: {}".format(traceback.format_exc()))
            product['buyer_reviews'] = BuyerReviews(*ZERO_REVIEWS_VALUE)

        return product

    @staticmethod
    def _parse_title(response):
        title = is_empty(response.xpath('//h1[@itemprop="name"]'
                                        '/text()').extract())
        return title

    @staticmethod
    def _parse_sku(response):
        sku = is_empty(response.xpath('//input[@id="defaultChildSku"]/@value').extract())
        return sku

    @staticmethod
    def _parse_categories(response):
        categories_sel = response.xpath('//div[@class="breadcrumb clearfix"]/a/@title').extract()
        categories = [i.strip() for i in categories_sel]
        return categories[:-1] if categories else None

    @staticmethod
    def _parse_price(response):
        fullprice = None
        price = response.xpath('//meta[@itemprop="price"]/@content').extract()
        price = price[0].strip() if price else None
        if price:
            currency = response.xpath('//meta[@itemprop="priceCurrency"]/@content').extract()
            currency = currency[0] if currency else None
            if not currency and '£' in price:
                currency = "GBP"
            if not currency:
                currency = "USD"
            fullprice = Price(
                price=price,
                priceCurrency=currency
            )
        return fullprice

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath('//meta[@itemprop="image"]/@content').extract()
        if image_url:
            image_url = re.search('//(.*)', image_url[0], re.DOTALL)
            return image_url.group(1) if image_url else None

    def _parse_buyer_reviews(self, response):
        meta = response.meta.copy()
        product = meta['product']
        average_rating = meta['avg_rating']
        num_of_reviews = meta['review_count']

        if average_rating > 5:
            average_rating = 5

        rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}

        try:
            review_html = html.fromstring(
                re.search('"BVRRSecondaryRatingSummarySourceID":" (.+?)"},', response.body).group(1)
            )
            ratings = review_html.xpath("//*[contains(@class, 'BVRRHistAbsLabel')]/text()")[:5]
            for i, rating in enumerate(ratings):
                rating_by_star[str(5 - i)] = int(re.findall('\d+', rating)[0])

            buyer_reviews = {
                'num_of_reviews': num_of_reviews,
                'average_rating': round(average_rating, 1),
                'rating_by_star': rating_by_star
            }

            product['buyer_reviews'] = buyer_reviews
        except:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()), WARNING)
            return BuyerReviews(*ZERO_REVIEWS_VALUE)

        return product

    @staticmethod
    def _parse_out_of_stock(response):
        availability = is_empty(response.xpath('//input[contains(@id, "inventoryAvailability")]/@value').extract())
        return not bool(availability)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        product_data = response.meta['product_data']
        total = product_data.find_elements_by_xpath('//div[contains(text(), "We found")]') or \
                product_data.find_elements_by_xpath('//div[@class="pagenofn"]')
        if total:
            total_data = re.search('(?:found\s+|of\s+)(\d+)', total[0].get_attribute('innerHTML'), re.DOTALL)
            if total_data:
                total = int(total_data.group(1))
        return total if isinstance(total, int) else 0

    def _scrape_product_links(self, response):
        product_data = response.meta['product_data']
        links = product_data.find_elements_by_xpath(".//ul[@class='product-grid']"
                                                    "/li//div[@class='cat-list-img']/a")

        for link in links:
            link = link.get_attribute('href')
            yield urlparse.urljoin(response.url, link), SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        total_matches = response.meta.get('total_matches')
        results_per_page = self._scrape_results_per_page(response)
        if not results_per_page:
            results_per_page = 32
        current_page = response.meta.get('current_page', 1)
        if (total_matches and results_per_page
            and current_page < math.ceil(total_matches / float(results_per_page))):
            current_page += 1
            next_link = self.NEXT_URL.format(search_term=response.meta.get('search_term'),
                                             offset=(current_page - 1) * results_per_page)
            response.meta['current_page'] = current_page
            return Request(
                next_link,
                meta=response.meta,
                callback=self._parse_help
            )
