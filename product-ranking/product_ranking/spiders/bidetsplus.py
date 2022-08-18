from __future__ import division, absolute_import, unicode_literals

import urlparse
import traceback
import re

from scrapy.conf import settings
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty


class BidetsplusProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'bidetsplus_products'
    allowed_domains = ["www.bidetsplus.com"]

    SEARCH_URL = "https://www.bidetsplus.com/search.php?search_query={search_term}&Search="

    def __init__(self, *args, **kwargs):
        super(BidetsplusProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(response)
        if not brand and title:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        price = self._parse_price(response)
        product['price'] = price

        product['locale'] = "en-US"

        out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', out_of_stock)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        if categories:
            cond_set_value(product, 'department', categories[-1])

        buyer_reviews = self.parse_buyer_reviews(response)
        product['buyer_reviews'] = buyer_reviews

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath("//h1[@class='TitleHeading']/text()").extract()

        return title[0] if title else None

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath("//span[@itemprop='brand']/text()").extract()

        return brand[0] if brand else None

    @staticmethod
    def _parse_is_out_of_stock(response):
        stock_status = response.xpath('//*[@itemprop="availability"]/@href').extract()
        if stock_status and 'instock' in stock_status[0].lower():
            return False
        return True

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath("//div[@id='ProductBreadcrumb']//ul//li/a/text()").extract()

        return categories[1:] if categories else None

    @staticmethod
    def _parse_image_url(response):
        main_image = response.xpath("//div[@class='ProductThumbImage']//a/@href").extract()

        return main_image[0] if main_image else None

    def _parse_price(self, response):
        price = is_empty(response.xpath("//span[contains(@class, 'ProductPrice')]/text()").extract())
        if not price:
            return None
        try:
            return Price(price=float(price.replace(',', '').replace('$', '').strip()), priceCurrency='USD')
        except:
            self.log("Error while parsing price: {}".format(traceback.format_exc()))

    def parse_buyer_reviews(self, response):
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        buyer_reviews_info = {}

        # Count of Review
        num_of_reviews = is_empty(
            response.xpath("//span[@itemprop='reviewCount']/text()").extract(), 0)

        avarage_rating = is_empty(
            response.xpath("//meta[@itemprop='ratingValue']/@content").extract(), 0)

        rating_value_data = response.xpath("//h4[@class='ReviewTitle']//img/@src").extract()

        for rating_value in rating_value_data:
            rating_star = re.search('images/(.*?).png', rating_value)
            if rating_star:
                rating_star = rating_star.group(1)
                if rating_star:
                    rating_star = re.search('\d+', rating_star)
                    if rating_star:
                        rating_star = rating_star.group()
                        rating_by_star[rating_star] += 1

        if num_of_reviews:
            buyer_reviews_info = {
                'num_of_reviews': int(num_of_reviews),
                'average_rating': float(avarage_rating),
                'rating_by_star': rating_by_star
            }

        if buyer_reviews_info:
            return BuyerReviews(**buyer_reviews_info)
        else:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()))
            return BuyerReviews(**ZERO_REVIEWS_VALUE)

    def _scrape_total_matches(self, response):
        return None

    def _scrape_product_links(self, response):
        product_links = response.xpath("//div[@class='ProductDetails']//p[@class='p-name']//a/@href").extract()

        for item_url in product_links:
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath("//div[@class='CategoryPagination']//a[@class='nav-next']/@href").extract()

        if next_page:
            return urlparse.urljoin(response.url, next_page[0])