from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback
import urlparse

from scrapy import Request
from scrapy.log import WARNING
from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value,\
    FormatterWithDefaults
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words

class SuperdrugProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'superdrug_products'
    allowed_domains = ["www.superdrug.com"]

    SEARCH_URL = "http://www.superdrug.com/search?text={search_term}"

    REVIEW_URL = "http://api.bazaarvoice.com/data/batch.json" \
                 "?passkey=i5l22ijc8h1i27z39g9iltwo3&apiversion=5.5" \
                 "&displaycode=10798-en_gb&resource.q0=reviews" \
                 "&filter.q0=isratingsonly%3Aeq%3Afalse&filter.q0=productid%3Aeq%3A{product_id}" \
                 "&filter.q0=contentlocale%3Aeq%3Aen_GB%2Cen_US&sort.q0=relevancy%3Aa1&stats.q0=reviews" \
                 "&filteredstats.q0=reviews&include.q0=authors%2Cproducts"

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        was_now = self._parse_was_now(response)
        cond_set_value(product, 'was_now', was_now)

        product['locale'] = "en-US"

        description = self._parse_description(response)
        product['description'] = description

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self._category_name(response)
        product['department'] = category

        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        product_id = response.xpath("//input[@name='productID']/@value").extract()
        if product_id:
            product_id = product_id[0]
            return Request(self.REVIEW_URL.format(product_id=product_id),
                           dont_filter=True,
                           meta={'prod': product,
                                 'product_id': product_id},
                           callback=self.parse_buyer_reviews
                           )
        return product

    def _parse_title(self, response):
        title = response.xpath("//meta[@property='og:title']/@content").extract()
        return title[0] if title else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        brand = re.search("'brand': (.*?),", response.body)

        if brand:
            brand = brand.group(1).replace('\"', '')
        if not brand and title:
            brand = guess_brand_from_first_words(title)

        return brand

    def _parse_categories(self, response):
        categories = response.xpath("//div[contains(@class, 'breadcrumb')]//a/text()").extract()
        return categories[1:] if categories else None

    def _category_name(self, response):
        category = self._parse_categories(response)
        return category[-1] if category else None

    def _parse_description(self, response):
        description = response.xpath("//div[contains(@class, 'panel-body--sd-base')]/p").extract()
        return self._clean_text(''.join(description)) if description else None

    def _parse_image_url(self, response):
        image = response.xpath("//div[@class='zoomTile']//img/@src").extract()
        return urlparse.urljoin(response.url, image[0]) if image else None

    @staticmethod
    def _get_now_price(response):
        now = response.xpath('//span[@itemprop="price"]/text()').re('\d+(?:\.\d+)?')
        return now[0] if now else None

    @staticmethod
    def _get_was_price(response):
        was = response.xpath('//span[@class="strikethrough"]/text()').re('\d+(?:\.\d+)?')
        return was[0] if was else None

    def _parse_price(self, response):
        price_amount = self._get_now_price(response)
        if price_amount:
            return Price(price=price_amount, priceCurrency='GBP')

    def _parse_was_now(self, response):
        now = self._get_now_price(response)
        was = self._get_was_price(response)
        if now and was:
            return '{}, {}'.format(now, was)

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = re.search(r'/p/(\d+)', response.url)
        return reseller_id.group(1) if reseller_id else None

    @staticmethod
    def _parse_out_of_stock(response):
        oos = re.search(r"\'in\sstock\':\s\'(.*?)\'", response.body)
        return oos.group(1) == 'outOfStock' if oos else False

    def parse_buyer_reviews(self, response):
        product = response.meta['prod']
        product_id = response.meta['product_id']
        zero_reviews_value = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        try:
            data = json.loads(response.body_as_unicode())

            results = data.get('BatchedResults', {}).get('q0', {}).get('Includes', {}).get('Products', {}).get(product_id, {})

            if results:
                data = results.get('FilteredReviewStatistics')
                review_count = data.get('TotalReviewCount')

                rating_by_star = {}
                stars = data.get("RatingDistribution", [])
                for star in stars:
                    rating_by_star[star['RatingValue']] = star['Count']

                average_rating = data.get("AverageOverallRating", 0)

                buyer_reviews = {
                    'num_of_reviews': review_count,
                    'average_rating': round(float(average_rating), 1) if average_rating else 0,
                    'rating_by_star': rating_by_star
                }

            else:
                buyer_reviews = zero_reviews_value

        except Exception:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()), WARNING)
            buyer_reviews = zero_reviews_value

        product['buyer_reviews'] = BuyerReviews(**buyer_reviews)

        return product

    def _scrape_total_matches(self, response):
        total_match = response.xpath("//p[@class='nomargin']/text()").re('\d+')

        return int(total_match[0]) if total_match else 0

    def _scrape_product_links(self, response):
        self.product_links = response.xpath('.//*[contains(@class, "name")]/@href').extract()

        for item_url in self.product_links:
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page_link = response.xpath(".//*[contains(@class, 'next')]//a/@href").extract()
        if next_page_link:
            return urlparse.urljoin(response.url, next_page_link[0])

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()