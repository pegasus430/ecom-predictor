from __future__ import absolute_import, division, unicode_literals

import re
import json
import string
import urlparse
import traceback

from scrapy.log import INFO
from scrapy.conf import settings

from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider, cond_replace_value,
                                     cond_set_value)
from product_ranking.utils import is_empty
from product_ranking.validation import BaseValidator


class OverstockProductsSpider(BaseValidator, BaseProductsSpider):

    name = 'overstock_products'
    allowed_domains = ["www.overstock.com", "overstock.com"]

    SEARCH_URL = "https://www.overstock.com/search?keywords={search_term}"

    def __init__(self, *args, **kwargs):
        super(OverstockProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        self.user_agent = "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)"

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

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
        cond_set_value(product, 'brand', brand)

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

        # Parse stock status
        is_out_of_stock = self._parse_stock_status(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # reseller_id
        cond_set_value(product, 'reseller_id', sku)

        canonical_url = self._parse_url(response)
        cond_replace_value(product, 'url', canonical_url)

        # review
        buyer_reviews = self._parse_reviews(response)
        cond_set_value(product, 'buyer_reviews', buyer_reviews)

        # variants
        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        return product

    def _parse_variants(self, response):
        variants_regex = re.compile(r'os\.optionBreakout\.options\s*=\s*(\[\{.+?\}\])\s*;')
        variants_raw = variants_regex.search(response.body_as_unicode())
        if variants_raw:
            try:
                variants_json = json.loads(variants_raw.group(1))
                return self._build_variants(variants_json)
            except:
                self.log(traceback.format_exc())

    @staticmethod
    def _build_variants(variants_json):
        variants = []
        for variant_raw in variants_json:
            variant = {'properties': {}}
            variant['in_stock'] = variant_raw.get('inStock')
            variant['price'] = variant_raw.get('pricingContext', {}).get('sellingPriceFormatted')
            variant['properties']['name'] = variant_raw.get('description')
            variant['sku'] = variant_raw.get('id')
            variants.append(variant)
        return variants

    def _parse_reviews(self, response):
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        num_of_reviews = response.xpath("//span[@class='count']/text()").re('\d+')
        # Count of Review
        if num_of_reviews:
            num_of_reviews = int(num_of_reviews[0])
        else:
            num_of_reviews = 0

        rating_values = []
        rating_counts = []

        # Get mark of Review
        rating_values_data = response.xpath("//div[@class='col-xs-2']//div[@class='label']/text()").extract()
        if rating_values_data:
            for rating_value in rating_values_data:
                rating_values.append(int(re.findall(r'(\d+)', rating_value)[0]))

        # Get count of Mark
        rating_count_data = response.xpath("//div[@class='append']/text()").extract()
        if rating_count_data:
            for rating_count in rating_count_data:
                rating_counts.append(int(re.findall(r'(\d+)', rating_count)[0]))

        if rating_counts:
            rating_counts = list(reversed(rating_counts))

        if len(rating_counts) == 5:
            rating_by_star = {'1': rating_counts[0], '2': rating_counts[1],
                              '3': rating_counts[2], '4': rating_counts[3], '5': rating_counts[4]}
        else:
            rating_by_star = {}

        avarage_rating = response.xpath('//div[@class="overall-rating"]/text()').re('\d+\.?\d*')

        if avarage_rating:
            average_rating = float(avarage_rating[0])
        else:
            average_rating = 0

        if rating_by_star:
            buyer_reviews_info = {
                'num_of_reviews': int(num_of_reviews),
                'average_rating': float(average_rating),
                'rating_by_star': rating_by_star
            }
            return BuyerReviews(**buyer_reviews_info)
        else:
            return BuyerReviews(**ZERO_REVIEWS_VALUE)


    @staticmethod
    def _parse_url(response):
        canonical_url = response.xpath('//link[@rel="canonical"]/@href').extract()
        if canonical_url:
            return urlparse.urljoin(response.url, canonical_url[0])

    @staticmethod
    def _parse_title(response):
        title = is_empty(response.xpath('//meta[@property="og:title"]'
                                        '/@content').extract())
        return title

    @staticmethod
    def _parse_brand(response):
        brand = is_empty(response.xpath('//meta[@itemprop="brand"]/@content').extract())
        return brand

    def _parse_categories(self, response):
        categories_sel = response.xpath('//div[@id="breadcrumbs"]/ul/li'
                                             '/a/span/text()').extract()
        categories = [i.strip() for i in categories_sel]
        return categories

    def _parse_currency(self, response):
        price_currency = response.xpath("//meta[@itemprop='priceCurrency']/@content").extract()
        return price_currency[0] if price_currency else 'USD'

    def _parse_price(self, response):
        currency = self._parse_currency(response)
        price = is_empty(response.xpath('//span[@itemprop="price"]'
                                        '/@content').extract(), "0.0")
        return Price(price=price, priceCurrency=currency) if price else None

    def _parse_image_url(self, response):
        image_url = is_empty(response.xpath('//meta[@property="og:image"]'
                                            '/@content').extract())
        return image_url

    def _parse_stock_status(self, response):
        return bool(response.xpath('//link[@itemprop="availability" '
                                   'and @href="http://schema.org/OutOfStock"]'))

    def _parse_sku(self, response):
        sku = re.search("products/(\d+)", response.url)
        return sku.group(1) if sku else None

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        total_matches = re.search("product result count: (\d+)", response.body_as_unicode())

        if total_matches:
            try:
                return int(total_matches.group(1))
            except:
                self.log(traceback.format_exc())
        else:
            return 0
        return

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//a[contains(@class,"product-link")]/@href').extract()

        if items:
            for item in items:
                res_item = SiteProductItem()
                yield item, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath("//div[contains(@class, 'pagination-btn')]"
                                   "//a[@class='next']/@href").extract()
        if next_page:
            return urlparse.urljoin(response.url, next_page[0])
