import json
import re
import traceback
import urlparse

from scrapy import Request
from scrapy.conf import settings

from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults
from product_ranking.utils import (catch_dictionary_exception,
                                   catch_json_exceptions)


class StaplesProductsSpider(BaseProductsSpider):
    name = 'staples_products'
    allowed_domains = ['www.staples.com', 'static.www.turnto.com']

    # Urls
    REVIEW_URL = 'https://static.www.turnto.com/sitedata/jwmno8RkY7SXz4jsite/v4_3/{sku}/d/en_US/catitemreviewshtml'
    SEARCH_URL = 'https://www.staples.com/{search_term}/directory_{search_term}?pn={page}&sby=0&akamai-feo=off'
    SHELF_URL = 'https://www.staples.com/{directory_name}/cat_{category_id}?pn={page}'
    PRODUCT_URL = 'https://www.staples.com/product_{sku}'

    def __init__(self, *args, **kwargs):
        super(StaplesProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            url_formatter=FormatterWithDefaults(
                page=1
            ),
            *args,
            **kwargs
        )
        settings.overrides['DEFAULT_REQUEST_HEADERS'] = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en',
            'X-Forwarded-For': '127.0.0.1'
        }
        settings.overrides['USE_PROXIES'] = True
        self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) ' \
                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'

        if getattr(self, 'product_url', None) and getattr(self, 'name') == 'staples_products':
            self.product_url = self.get_product_url(self.product_url)

    def start_requests(self):
        for request in super(StaplesProductsSpider, self).start_requests():
            if self.searchterms:
                request = request.replace(callback=self.parse_search)
            yield request

    def parse_search(self, response):
        redirect = response.xpath('//div[@id="redirect"]')
        if redirect:
            category_url = re.findall("\.replace\('(.*?)'\)", response.body)
            if category_url:
                url = urlparse.urljoin(response.url, category_url[0])
                return Request(url, meta=response.meta)
            else:
                return
        else:
            return self.parse(response)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta.get('product')
        product['not_found'] = not self.is_valid_url(response.request.url)

        if product['not_found']:
            yield product
            return

        data = self.extract_json_data(response)

        product.update(
            {
                'title': self.parse_title(data),
                'categories': self.parse_categories(data),
                'zip_code': self.parse_zip_code(data),
                'image_url': self.parse_image_url(data),
                'upc': self.parse_upc(data),
                'sku': self.parse_sku(data),
                'model': self.parse_model(data),
                'price': self.parse_price(data),
                'brand': self.parse_brand(data),
                'is_out_of_stock': self.parse_is_out_of_stock(data),
                'url': self.parse_url(data),
                'reseller_id': self.parse_sku(data)
            }
        )
        if product['sku'] and self.is_there_product_reviews(data):
            yield Request(
                self.REVIEW_URL.format(
                    sku=product['sku']
                ),
                callback=self.parse_buyer_reviews,
                meta=response.meta
            )
            return
        yield product

    def get_product_url(self, url):
        sku = re.search('product_([^/]+)', url)
        if sku:
            return self.PRODUCT_URL.format(
                sku=sku.group(1)
            )

    @catch_dictionary_exception
    def is_there_product_reviews(self, data):
        return bool(data['product']['review']['count'])

    def parse_buyer_reviews(self, response):
        product = response.meta.get('product')
        try:
            buyer_reviews = BuyerReviews(
                rating_by_star={
                    index: int(response.xpath(
                        '//div[@id="TTreviewSummaryBreakdown-{}"]/text()'.format(index)
                    ).extract()[0]) for index in range(1, 5+1)
                    },
                num_of_reviews=int(response.xpath('//div[@class="TTreviewCount"]/text()').re('[\d,]+')[0].replace(',', '')),
                average_rating=float(response.xpath('//span[@id="TTreviewSummaryAverageRating"]').re('\d\.\d')[0])
            )
            product['buyer_reviews'] = buyer_reviews
        except:
            self.log('Something is wrong with reviews extraction: {}'.format(traceback.format_exc()))
        return product

    # Check if product_url correct
    @staticmethod
    def is_valid_url(url):
        return re.match('https?://www.staples.com/(?:.*/)?product_([^/]+)', url.split('?')[0])

    # Extract json block
    @catch_json_exceptions
    def extract_json_data(self, response):
        return json.loads(response.xpath('//div[@id="analyticsItemData"]/@content').extract()[0])

    # Parse fields from json block above
    @catch_dictionary_exception
    def parse_url(self, data):
        return data['product']['seoData']['canonical']

    @catch_dictionary_exception
    def parse_title(self, data):
        return data['product']['name']

    @catch_dictionary_exception
    def parse_categories(self, data):
        return [breadcrumb['displayName'] for breadcrumb in data['product']['breadcrumb']]

    @catch_dictionary_exception
    def parse_zip_code(self, data):
        return data['price']['zipCode']

    @catch_dictionary_exception
    def parse_price(self, data):
        def parse_currency(data):
            return data['price']['currency']
        def parse_amount(data):
            return data['price']['item'][0]['finalPrice']
        return Price(
            priceCurrency=parse_currency(data),
            price=parse_amount(data)
        )

    @catch_dictionary_exception
    def parse_image_url(self, data):
        return data['product']['images']['standard'][0].replace('?$std$', '')

    @catch_dictionary_exception
    def parse_upc(self, data):
        return data['product']['upcCode']

    @catch_dictionary_exception
    def parse_model(self, data):
        return data['product']['manufacturerPartNumber']

    @catch_dictionary_exception
    def parse_sku(self, data):
        return data['itemID']

    @catch_dictionary_exception
    def parse_brand(self, data):
        return data['product']['manufacturerName']

    @catch_dictionary_exception
    def parse_is_out_of_stock(self, data):
        return data['inventory']['items'][0]['productIsOutOfStock']

    # Search component
    def get_search_term_url(self, search_term, page):
        return self.SEARCH_URL.format(search_term=search_term, page=page)

    def _scrape_product_links(self, response):
        sku_list = response.xpath(
            '//div[@class="stp--new-product-tile-container desktop"]/div[@class="tile-container"]/@id'
        ).extract()
        for sku in sku_list:
            yield self.PRODUCT_URL.format(sku=sku), SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if response.xpath('//input[@id="lastPage" and @value="false"]'):
            next_page = int(response.xpath('//input[@id="pagenum"]/@value').extract()[0]) + 1
            return self.get_search_term_url(
                response.meta['search_term'],
                next_page
            )

    def _scrape_total_matches(self, response):
        try:
            return int(response.xpath('//span[@class="results-number"]/text()').re('\d+')[0])
        except:
            self.log('Can not parse total matches from page: {}'.format(traceback.format_exc()))
            return
