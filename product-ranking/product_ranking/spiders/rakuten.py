import re
import json
import traceback
from urlparse import urljoin

from scrapy import Request
from scrapy.conf import settings
from scrapy.log import WARNING

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import (BaseProductsSpider, cond_set_value,
                                     FormatterWithDefaults)
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty


class RakutenProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'rakuten_products'
    allowed_domains = ["rakuten.com"]

    SEARCH_URL = "https://www.rakuten.com/search/{search_term}/"

    HEADERS = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'accept-encoding': 'gzip, deflate, sdch, br',
        'accept-language': 'en-US,en;q=0.8',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'
    }

    def __init__(self, *args, **kwargs):
        settings.overrides['USE_PROXIES'] = True
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares
        settings.overrides['DOWNLOAD_DELAY'] = 1
        settings.overrides['CONCURRENT_REQUESTS'] = 2
        settings.overrides['COOKIES_ENABLED'] = False
        settings.overrides['REFERER_ENABLED'] = False
        super(RakutenProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(num_page=1),
            *args, **kwargs)

    def start_requests(self):
        for request in super(RakutenProductsSpider, self).start_requests():
            request = request.replace(headers=self.HEADERS, dont_filter=True)
            if not self.product_url:
                st = request.meta.get('search_term', '')
                url = self.SEARCH_URL.format(search_term=st)
                request = request.replace(url=url)
            yield request

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        try:
            data = json.loads(re.search("'page_info': (.*?)\}\)", response.body_as_unicode()).group(1)).get('page_products')
        except:
            self.log('JSON not found or invalid JSON: {}'.format(traceback.format_exc()))
            product['not_found'] = True
            return product

        is_out_of_stock = not bool(data.get('stock_available'))
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        no_longer_available = data.get('productNoLongerSold', '')
        cond_set_value(product, 'no_longer_available', 'True' in no_longer_available)

        title = is_empty(response.xpath(
            "//meta[@property='og:title']/@content").extract())
        cond_set_value(product, 'title', title)

        price = data.get('prod_price')
        if price:
            currency = data.get('currency', 'USD')
            cond_set_value(product, 'price', Price(currency, price))

        brand = data.get('brand')
        if not brand and title:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        categories = response.xpath(
            '//div[@class="product-breadcrumbs"]//a/text() | '
            '//ul[contains(@class, "b-breadcrumb")]//a/span/text()').extract()
        if categories:
            cond_set_value(product, 'categories', categories)
            cond_set_value(product, 'department', categories[-1])

        product['locale'] = "en-US"
        product['sku'] = data.get('prod_id')

        product['reseller_id'] = data.get('prod_id')

        product['image_url'] = data.get('prod_image_url')

        desc = is_empty(response.xpath("//div[@class='b-description']//p/text()").extract())
        cond_set_value(product, 'description', desc)

        upc = self.parse_upc(data)
        cond_set_value(product, 'upc', upc)

        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        if product.get('is_single_result'):
            review_url = response.xpath("//div[contains(@class, 'shop-review')]//a/@href").extract()
            if review_url:
                return Request(
                    url=review_url[0],
                    callback=self.parse_buyer_reviews,
                    headers=self.HEADERS,
                    meta=response.meta,
                    dont_filter=True
                )

        return product

    def parse_upc(self, data):
        upc = data.get('gtin')
        if upc:
            upc = re.search('\d+', upc[0])
            return upc.group() if upc else None

    def _parse_variants(self, response):
        try:
            items = json.loads(
                re.search(
                    'productAttributes\s*=\s*(\[.*\])',
                    response.body_as_unicode()
                ).group(1)
            )
        except:
            self.log('JSON not found or invalid JSON: {}'.format(traceback.format_exc()), WARNING)
            return None

        variants = []
        for item in items:
            properties = {}
            for option in item.get('Attributes', {}).itervalues():
                option = response.xpath('//option[@value="{}"]'.format(option))
                value = is_empty(option.xpath('text()').extract())
                key = is_empty(option.xpath(
                    './/ancestor::div[@class="attr-selector"]/label/text()'
                ).extract())
                if key and value:
                    properties[key] = value

            properties['sku'] = item.get('Sku')
            variant = {'properties': properties, 'in_stock': item.get('IsAvailable')}
            variants.append(variant)

        return variants

    def parse_buyer_reviews(self, response):
        meta = response.meta.copy()
        product = meta['product']

        rating_list = []
        buyer_reviews = meta.get('buyer_reviews')
        if meta.get('review_list'):
            review_list = meta.get('review_list')
        else:
            review_list = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}

        if not buyer_reviews:
            num_of_reviews = is_empty(response.xpath("//b[@class='b-text-large']/text()").re('([\d,]+)\sReviews'), 0)
            num_of_reviews = int(num_of_reviews)
            average_rating = is_empty(response.xpath('//dl[@class="b-dl-inline"]//span[@class="b-text-sub"]/text()')
                                      .re('([\d.,]+)\sout'), '0.0')
            average_rating = round(float(average_rating), 0)

        ratings = response.xpath("//span[@class='b-rating']")
        for rating in ratings:
            rating_list.append(len(rating.xpath('.//span[contains(@class, "b-star-full")]')))
        for i in rating_list:
            review_list[str(i)] += 1

        meta['review_list'] = review_list
        if not buyer_reviews:
            buyer_reviews = {
                'num_of_reviews': num_of_reviews,
                'average_rating': average_rating,
                'rating_by_star': review_list,
            }
        else:
            buyer_reviews['rating_by_star'] = review_list

        meta['buyer_reviews'] = buyer_reviews
        review_next_url = response.xpath('//a[@id="right_arrow"]/@href').extract()
        if review_next_url:
            return Request(
                url=review_next_url[0],
                dont_filter=True,
                callback=self.parse_buyer_reviews,
                headers=self.HEADERS,
                meta=meta,
            )

        product['buyer_reviews'] = BuyerReviews(**buyer_reviews) if buyer_reviews else ZERO_REVIEWS_VALUE
        return product

    def _scrape_total_matches(self, response):
        totals = response.xpath(
                '//div[@class="total_results"]/span'
            ).re('(\d+)\+? items')
        if not totals:
            totals = is_empty(
                response.xpath('//div[@class="b-tabs-utility"]/text()').re('of\s(\d{1,3}[,\d{3}]*)')
            )
        if not totals:
            totals = is_empty(
                response.xpath('//span[contains(@class, "r-search-page__hits")]/text()').re('of\s(\d{1,3}[,\d{3}]*)')
            )
        if totals:
            return int(totals.replace(',', ''))

    def _scrape_product_links(self, response):
        links = response.xpath('//div[@class="item"]/div/a/@href | '
                               '//div[contains(@class, "b-content")]/b/a/@href |'
                               '//div[contains(@class, "r-product")]//div[contains(@class, "r-product__name")]/a/@href').extract()
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page = is_empty(
            response.xpath(
                '//*[contains(@class, "chevron-right")]/parent::a/@href | '
                '//a[@id="pagen_right"]/@href'
            ).extract()
        )
        if next_page:
            return Request(
                urljoin(response.url, next_page),
                meta=response.meta,
                headers=self.HEADERS,
                dont_filter=True
            )

    def _get_products(self, response):
        for req in super(RakutenProductsSpider, self)._get_products(response):
            yield req.replace(headers=self.HEADERS, dont_filter=True)
