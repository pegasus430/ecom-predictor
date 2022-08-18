import re
import string
import urlparse

from itertools import islice
from scrapy import Request
from scrapy.log import ERROR, INFO

from product_ranking.utils import is_empty
from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import cond_set_value
from product_ranking.spiders.contrib.product_spider import ProductsSpider
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi



class PepboysProductsSpider(ProductsSpider):
    name = 'pepboys_products'
    allowed_domains = ['pepboys.com']

    SEARCH_URL = "https://www.pepboys.com/search/?term={search_term}"

    def __init__(self, *args, **kwargs):
        super(PepboysProductsSpider, self).__init__(*args, **kwargs)
        self.br = BuyerReviewsBazaarApi(called_class=self)

    def _total_matches_from_html(self, response):
        item_urls = response.xpath(
            '//div[@class="j-results-item"]//a[@class="tirePicLink"]/@href'
        ).extract()
        return len(item_urls) if item_urls else '0'

    def _scrape_product_links(self, response):
        item_urls = response.xpath(
            '//div[@class="j-results-item"]//a[@class="tirePicLink"]/@href'
        ).extract()
        for item_url in item_urls:
            yield item_url, SiteProductItem()

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _parse_title(self, response):
        title = response.xpath('//h4[contains(@class,"margin-top-none")]//text()').extract()
        title = [r.strip() for r in title if len(r.strip())>0]
        title = "".join(title)
        return title.strip() if title else None

    def _parse_categories(self, response):
        categories = response.xpath(
            '//*[@class="breadcrumb"]//li/a/text()'
        ).extract()
        return categories if categories else None

    def _parse_category(self, response):
        categories = self._parse_categories(response)
        return categories[-1] if categories else None

    def _parse_price(self, response):
        try:
            price = response.xpath(
                '//div[contains(@class,"subtotal")]//span[@class="price"]//text()'
            ).extract()[0].strip()
            price = re.findall(r'[\d\.]+', price)
        except:
            return None
        if not price:
            return None
        return Price(price=price[0], priceCurrency='USD')

    def _parse_image_url(self, response):
        image_url = response.xpath(
            '//img[contains(@class,"tdTireDetailImg")]/@src'
        ).extract()
        return image_url[0] if image_url else None

    def _parse_brand(self, response):
        brand = 'Pepboys'
        return brand.strip() if brand else None

    def _parse_sku(self, response):
        sku = response.xpath(
            '//div[contains(@class,"j-results-item-container")]/@data-sku'
        ).extract()
        return sku[0] if sku else None

    def _parse_variants(self, response):
        return None

    def _parse_is_out_of_stock(self, response):
        status = response.xpath(
            '//*[@id="availability"]/span[text()="In Stock"]')

        return not bool(status)

    def _parse_shipping_included(self, response):
        shipping_text = ''.join(
            response.xpath('//span[@class="free-shipping"]//text()').extract())

        return shipping_text == ' & FREE Shipping'

    def _parse_description(self, response):
        description = response.xpath(
            '//div[contains(@class,"tdContentDesc")]'
        ).extract()

        return ''.join(description).strip() if description else None

    def _parse_buyer_reviews(self, response):
        buyer_reviews = None
        num_of_reviews = int(is_empty(response.xpath(
            '//span[@class="bvseo-reviewCount"]/text()'
        ).extract(), '0'))
        if num_of_reviews:
            average_rating = float(is_empty(response.xpath(
                '//span[@class="bvseo-ratingValue"]/text()'
            ).extract()))

            buyer_reviews = BuyerReviews(
                num_of_reviews=num_of_reviews,
                average_rating=average_rating,
                rating_by_star={}
            )

        return buyer_reviews

    def parse_product(self, response):
        product = response.meta['product']
        response.meta['product_response'] = response
        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse category
        category = self._parse_category(response)
        cond_set_value(product, 'category', category)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse variants
        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        # Parse stock status
        out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', out_of_stock)

        # Sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # Shipping included
        shipping_included = self._parse_shipping_included(response)
        cond_set_value(product, 'shipping_included', shipping_included)

        buyer_reviews = self._parse_buyer_reviews(response)
        cond_set_value(product, 'buyer_reviews', buyer_reviews)

        return product
