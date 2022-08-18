from __future__ import division, absolute_import, unicode_literals

import re
import urlparse
import urllib
import json
import traceback
from scrapy.http import Request
from scrapy.log import WARNING

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words
from spiders_shared_code.cymax_variants import CymaxVariants
from product_ranking.utils import is_empty


class CymaxProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'cymax_products'
    allowed_domains = ["www.cymax.com"]

    SEARCH_URL = "https://www.cymax.com/{search_term}--C0.htm?q={search_term}"

    REVIEW_URL = "https://www.cymax.com/WebService/WService.svc/Reviews_Get"

    def start_requests(self):
        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=st,
                ),
                meta={'search_term': st, 'remaining': self.quantity},
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod})

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = response.xpath("//div[@id='product-title-review']//h1/text()").extract()
        cond_set_value(product, 'title', title[0] if title else None)

        brand = self._parse_brand(response)
        if not brand:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        image_url = response.xpath("//div[@id='product-image-area']//img/@src").extract()
        cond_set_value(product, 'image_url', image_url[0] if image_url else None)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        product['locale'] = "en-US"

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        product_id = response.xpath("//input[@name='Main.ProdID']/@value").extract()
        review_info = self._parse_single_review(response)

        cymax_variants = CymaxVariants()
        cymax_variants.setupSC(response)
        variants = cymax_variants._variants()
        cond_set_value(product, 'variants', variants)
        cond_set_value(product, 'reseller_id', sku)

        if all([product_id, review_info]):
            payload = {"productId": product_id[0]}
            return Request(
                url=self.REVIEW_URL,
                callback=self.parse_buyer_reviews,
                method='POST',
                headers={'Content-Type': 'application/json'},
                meta={"product": product, "review_info": review_info},
                body=json.dumps(payload),
                dont_filter=True
            )

        return product

    def _parse_brand(self, response):
        brand = response.xpath("//div[@id='aboutBrand']//img[@alt='Brand Logo']/@title").extract()

        if brand:
            return brand[0]

    def _parse_categories(self, response):
        categories = response.xpath("//ol[contains(@class, 'breadcrumb')]//li/a/text()").extract()

        return categories[1:] if categories else None

    def _parse_sku(self, response):
        sku = response.xpath("//div[@id='product-codes-area']//span/text()").re(r'\d+')
        return sku[0] if sku else None

    def parse_buyer_reviews(self, response):
        rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        rating_values = []
        product = response.meta['product']
        review_info = response.meta['review_info']

        try:
            review_json = json.loads(response.body)
            if 'd' in review_json:
                review_json = json.loads(review_json['d'])
        except:
            self.log("Could not get JSON match.", WARNING)
            review_json = None

        if review_json:
            rating_values = review_json

        for rating in rating_values:
            rating_by_star[str(rating['OverallRating'])] += 1

        if rating_by_star:
            buyer_reviews = {
                'num_of_reviews': review_info['num_of_reviews'],
                'average_rating': review_info['average_rating'],
                'rating_by_star': rating_by_star
            }

            product['buyer_reviews'] = BuyerReviews(**buyer_reviews)

        return product

    def _parse_single_review(self, response):
        num_of_reviews = response.xpath("//div[@itemprop='rating']/text()").extract()
        if num_of_reviews:
            num_of_reviews = re.search('\d+', num_of_reviews[0]).group()
        else:
            num_of_reviews = response.xpath(
                '//div[@id="review-resume"]//span/text()'
            ).re('Based on (\d{1,3}[\,\d{3}]*) review')
            num_of_reviews = num_of_reviews[0] if num_of_reviews else 0

        average_rating = response.xpath(
            '//span[@class="rating-rounded-average badge"]/text() | '
            '//div[@id="review-resume"]//ul[@data-review-value]/@data-review-value'
        ).re('\d\.?\d*')

        average_rating = average_rating[0] if average_rating else 0

        if not all([num_of_reviews, average_rating]):
            return {}

        try:
            return {
                'num_of_reviews': int(num_of_reviews),
                'average_rating': float(average_rating)
            }
        except:
            self.log('Parsing Error Of Review Info: {}'.format(traceback.format_exc()), WARNING)
            return {}

    def _parse_price(self, response):
        price = response.xpath("//*[@id='product-main-price']/text()").re(FLOATING_POINT_RGEX)
        price_currency = is_empty(response.xpath("//meta[@property='og:price:currency']/@content").extract(), 'USD')

        if price:
            return Price(priceCurrency=price_currency, price=price[0])

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    def _scrape_total_matches(self, response):
        total_matches = response.xpath("//span[@class='filter-count hidden-xs']/text()").extract()
        if total_matches:
            total_matches = re.search('\d+', total_matches[0]).group()
        return int(total_matches) if total_matches else None

    def _scrape_product_links(self, response):
        links = response.xpath("//ul[@id='products-list']"
                               "//li[contains(@class, 'list-item')]"
                               "//a[@class='link']/@href").extract()

        for item_url in links:
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page_link = response.xpath("//ul[contains(@class, 'pagination')]//a[@rel='next']/@href").extract()
        if next_page_link:
            return urlparse.urljoin(response.url, next_page_link[0])
