# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import urlparse

from scrapy.log import INFO
from scrapy.conf import settings
from scrapy import Request

from product_ranking.items import (SiteProductItem, Price)
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty, _find_between
from product_ranking.powerreviews import parse_powerreviews_buyer_reviews
from spiders_shared_code.modcloth_variants import ModClothVariants


class ModClothProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'modcloth_products'
    allowed_domains = ["www.modcloth.com", "modcloth.com", "readservices.powerreviews.com"]

    REVIEW_URL = "http://readservices-b2c.powerreviews.com/m/{pwr_group_id}/l/en_US/product/{pwr_product_id}" \
                 "/reviews?apikey={api_key}"

    HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/58.0.3029.81 Safari/537.36"}

    SEARCH_URL = "https://www.modcloth.com/on/demandware.store/Sites-modcloth-Site" \
                 "/default/Search-Show?q={search_term}&lang=default"

    def __init__(self, *args, **kwargs):
        super(ModClothProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        self.price = None

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        brand = self._parse_brand(response)
        if not brand:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse price
        price = self._parse_price(self, response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        no_longer_available = self._parse_no_longer_available(response)
        product["no_longer_available"] = no_longer_available

        if no_longer_available:
            product["is_out_of_stock"] = True
        else:
            is_out_of_stock = self._is_out_of_stock(response)
            product["is_out_of_stock"] = is_out_of_stock

        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        product_id = self._parse_product_id(response)
        cond_set_value(product, 'reseller_id', product_id)

        reviews_apikey = self._parse_reviews_apikey(response)
        pwr_group_id = _find_between(response.body, '"POWERREVIEWS_MERCHANT_ID":"', '"')
        pwr_product_id = _find_between(response.body, '"variationGroupID": "', '"')

        # Parse buyer reviews
        if reviews_apikey and pwr_group_id and pwr_product_id:
            return Request(
                self.REVIEW_URL.format(
                    pwr_group_id=pwr_group_id,
                    pwr_product_id=pwr_product_id,
                    api_key=reviews_apikey
                ),
                dont_filter=True,
                meta=response.meta,
                callback=self._parse_buyer_reviews,
                headers=self.HEADERS
            )

        return product

    @staticmethod
    def _parse_brand(response):
        return is_empty(response.xpath('//span[@class="product-brand"]/a/text()').extract())

    @staticmethod
    def _parse_reviews_apikey(response):
        key = re.search(r'"POWERREVIEWS_API_KEY":"(.*?)"', response.body)
        if key:
            return key.group(1)

    @staticmethod
    def _parse_product_id(response):
        prod_id = is_empty(response.xpath('//div[@class="product-number"]/span/text()').extract())
        return prod_id

    @staticmethod
    def _parse_title(response):
        title = is_empty(response.xpath('//h1[contains(@class, "product-name")]'
                                        '/text()').extract())
        return title

    @staticmethod
    def _parse_model(response):
        model = is_empty(response.xpath('//div[contains(@class, "short-description")]'
                                        '/span[@class="h4"]/text()').extract())
        r = re.compile('(\d+)')

        if model:
            model = filter(r.match, model)
            return model

    @staticmethod
    def _parse_categories(response):
        categories_sel = response.xpath('//div[contains(@class, "breadcrumb")]/a/text()').extract()
        categories = [i.strip() for i in categories_sel]
        return categories

    @staticmethod
    def _parse_price(self, response):
        currency = "USD"

        try:
            price = None
            price_sales = is_empty(response.xpath('//div[contains(@class, "product-price")]'
                                                  '//span[@class="price-sales"]'
                                                  '/text()').extract())
            price_promo = is_empty(response.xpath('//div[contains(@class, "product-price")]'
                                                  '//span[@class="price-promo"]'
                                                  '/text()').extract())
            price_range = is_empty(response.xpath('//div[contains(@class, "product-price")]'
                                                  '/div/text()').extract())

            if price_sales:
                price = price_sales

            elif price_promo:
                price = price_promo

            elif price_range:
                price = price_range.strip().split('-')[0]

            self.price = float(price.replace("$", ''))
            return Price(price=self.price, priceCurrency=currency)

        except:
            return None

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath('//div[contains(@class, "product-primary-image")]'
                                   '//img[contains(@class, "primary-image")]/@src').extract()
        if image_url:
            return image_url[0]

    def _parse_no_longer_available(self, response):
        arr = response.xpath('//div[@class="item-na"]/text()').extract()
        if "is no longer available." in " ".join(arr):
            return True
        else:
            arr = response.xpath('//span[@class="price-sales"]/text()').extract()
            if "N/A" in " ".join(arr):
                return True

        return False

    @staticmethod
    def _parse_buyer_reviews(response):
        product = response.meta.get('product')
        product['buyer_reviews'] = parse_powerreviews_buyer_reviews(response)

        return product

    def _is_out_of_stock(self, response):
        out_of_stock = response.xpath('//div[@class="availability-msg"]/p/@class').extract()
        if out_of_stock and "not-available" in out_of_stock[0]:
            return True

        stock_info = response.xpath('//*[@property="og:availability"]/@content').extract()
        if stock_info and "instock" not in stock_info[0]:
            return True

        return False

    @staticmethod
    def _parse_variants(response):
        mv = ModClothVariants()
        mv.setupSC(response)

        return mv._variants()

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        totals = response.xpath('//div[@class="pagination"]'
                                '/div/text()').extract()
        if totals:
            totals = re.search(r'(?:of)?(\d+) Results', totals[1].replace('\n', ''), re.DOTALL)
            return int(totals.group(1))

        else:
            return 0

    def _scrape_results_per_page(self, response):
        item_count = response.xpath('//div[@class="pagination"]'
                                    '/div/text()').extract()
        if item_count:
            item_count = re.search('-(\d+) of', item_count[1].replace('\n', ''), re.DOTALL)
            return int(item_count.group(1)) if item_count else 0

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//ul[contains(@id, "search-result-items")]'
                               '/li[contains(@class, "grid-tile")]'
                               '//a[@class="name-link"]/@href').extract()
        if not items:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

        for item in items:
            res_item = SiteProductItem()
            yield item, res_item

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath('//div[@class="page-next"]/@href').extract()
        if next_page:
            return urlparse.urljoin(response.url, next_page[0])
