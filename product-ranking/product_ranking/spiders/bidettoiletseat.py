from __future__ import division, absolute_import, unicode_literals

import re
import urlparse
import traceback

from scrapy.log import INFO, WARNING
from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words


class BidetToiletSeatProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'bidettoiletseat_products'
    allowed_domains = ["bidet-toilet-seat.com"]
    SEARCH_URL = "http://www.bidet-toilet-seat.com/search.asp?keyword={search_term}&search="

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        cond_set_value(
            product,
            'title',
            response.xpath("//h1[@class='page_headers']/text()").extract()[0])

        if not product.get('brand', None):
            brand = guess_brand_from_first_words(product.get('title', '').strip() if product.get('title') else '')
            cond_set_value(product, 'brand', brand)

        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        desc = self._parse_description(response)
        cond_set_value(product, 'description', desc)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        price, currency = self._parse_price(response)
        product['price'] = Price(price=float(price), priceCurrency=currency)

        is_out_of_stock = self._parse_stock_status(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        buyer_reviews = self.parse_buyer_reviews(response)
        product['buyer_reviews'] = buyer_reviews

        product['locale'] = "en-US"

        return product

    def _parse_description(self, response):
        description = response.xpath(
            "//div[@itemprop='description']//p"
        ).extract()
        description = ''.join(description)

        return description if description else None

    def _parse_categories(self, response):
        categories_list = response.xpath(
            "//div[contains(@class, 'breadcrumbs')]"
            "//a/text()"
        ).extract()
        categories = map(self._clean_text, categories_list)

        return categories[1:] if categories else None

    def _parse_price(self, response):
        currency = 'USD'
        price_info = response.xpath("//span[@id='price']/text()").extract()

        if price_info:
            price = price_info[0]
            if '$' in price:
                price = price.replace('$', '').strip()
            return price, currency
        return 0.00, currency

    def _parse_image(self, response):
        image_url = response.xpath("//div[@class='main-image']//a/@href").extract()
        if image_url:
            image_url = urlparse.urljoin(response.url, image_url[0])
            return image_url

    def _parse_stock_status(self, response):
        in_stock = response.xpath("//div[@id='availability']/text()").extract()
        if in_stock and in_stock[0].lower() == 'in stock.':
            return False
        return True

    def parse_buyer_reviews(self, response):
        rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}

        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        num_of_reviews_info = response.xpath(
            "//div[@class='review-count']"
            "//a//text()").extract()

        # Count of Review
        try:
            num_of_reviews = re.findall(r'(\d+)', num_of_reviews_info[0])[0]
        except:
            num_of_reviews = 0

        rating_values = []

        # Get mark of Review
        rating_values_data = response.xpath(
            "//div[@class='user_reviews']"
            "//div[@class='star-rating']"
            "//img/@alt").extract()

        for rating_value in rating_values_data:
            rating_values.append(int(re.findall(r'(\d+)', rating_value[0])[0]))

        for rating in rating_values:
            rating_by_star[str(rating)] += 1

        average_rating = response.xpath("//div[@class='review_average']/text()").extract()

        if average_rating:
            average_rating = average_rating[0]
        else:
            average_rating = 0

        buyer_reviews_info = {}
        if rating_by_star:
            buyer_reviews_info = {
                'num_of_reviews': int(num_of_reviews),
                'average_rating': float(average_rating),
                'rating_by_star': rating_by_star
            }

        if buyer_reviews_info:
            return BuyerReviews(**buyer_reviews_info)
        else:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()))
            return BuyerReviews(**ZERO_REVIEWS_VALUE)

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t]", "", text).strip()

    @staticmethod
    def _find_between(s, first, last, offset=0):
        try:
            s = s.decode("utf-8")
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""

    def _scrape_total_matches(self, response):
        total_info = response.xpath(
            "//div[@class='products-header']/text()").extract()
        try:
            total_matches = re.findall(r'(\d+)', total_info[0])[0]
            return int(total_matches)
        except:
            return 0

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//div[contains(@class, 'product-item')]"
            "//div[@class='img']"
            "//a/@href").extract()
        if links:
            for item_url in links:
                yield item_url, SiteProductItem()
        else:
            self.log("Found no product links in {url}".format(
                url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        url = response.xpath(
            "//*[@class='pages']"
            "//ul/li[contains(@class, 'current')]"
            "/following-sibling::li[1]/a/@href").extract()

        if url:
            return url[0]
        else:
            self.log("Found no 'next page' links", WARNING)
