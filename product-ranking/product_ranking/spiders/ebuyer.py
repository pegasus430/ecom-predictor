from __future__ import division, absolute_import, unicode_literals

import urlparse
import urllib
import json
import re

from scrapy import FormRequest
from scrapy.log import WARNING
from scrapy.http import Request

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import BaseProductsSpider, \
    FormatterWithDefaults, FLOATING_POINT_RGEX, dump_url_to_file
from product_ranking.utils import is_empty


class EBuyerProductSpider(BaseProductsSpider):
    """Spider for ebuyer.com.

    Allowed search orders:
    -'rating'
    -'price_asc'
    -'price_desc'
    -'default'

    Fields limited_stock, is_in_store_only, upc not provided.

    Also when cookies wasn't cleared at browser ebuyer may display
    category "Items Related to Your Recent Searches". Spider don't
    see this category.
    """
    name = 'ebuyer_products'
    allowed_domains = ["ebuyer.com"]

    SEARCH_URL = "http://www.ebuyer.com/search?q={search_term}"

    SEARCH_SORT = {
        'rating': 'rating descending',
        'price_asc': 'price ascending',
        'price_desc': 'price descending',
        'default': 'relevancy descending',
    }

    REVIEW_URL = "http://www.ebuyer.com/reevoo-ajax/{sku}"

    POPULATE_REVIEWS = True

    def __init__(self, search_sort='default', *args, **kwargs):
        self.order = self.SEARCH_SORT[search_sort]
        super(EBuyerProductSpider, self).__init__(
            url_formatter=FormatterWithDefaults(),
            *args,
            **kwargs)

    def start_requests(self):
        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                ),
                callback=self.sort_handling,
                meta={'search_term': st, 'remaining': self.quantity},
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod})

    def sort_handling(self, response):
        parsed = urlparse.urlparse(response.url)
        qs = urlparse.parse_qs(parsed.query)
        qs['sort'] = [self.order]
        new_query = urllib.urlencode(qs, doseq=True)
        new_parsed = parsed._replace(query=new_query)
        sorted_url = urlparse.urlunparse(new_parsed)
        return Request(sorted_url, callback=self.parse,
                       meta=response.meta.copy())

    def _scrape_total_matches(self, response):
        num_results = response.xpath(
            '//li[@class="listing-count"]/text()').re('(\d+)')
        if num_results and num_results[1]:
            total = int(num_results[1])
            if total == 1000:
                # Get approximate number of total matches.
                # Since the site doesn't provide it for search
                # result with number bigger than 1000
                total = 15*int(num_results[0])
            return total
        else:
            return 0

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//h3[@class="listing-product-title"]/a/@href').extract()
        if not links:
            self.log("Found no product links.", WARNING)
        for link in links:
            link = urlparse.urljoin(response.url, link)
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next = response.xpath(
            '//li[@class="next-page"]/a/@href').extract()
        if next and next[0]:
            next_url = next[0] + '&sort=' + self.order
            return urlparse.urljoin(response.url, next_url)
        else:
            return None

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        prod = response.meta['product']

        prod['url'] = response.url
        prod['locale'] = 'en_GB'

        title = response.xpath(
            '//h1[@class="product-title"]/text()').extract()
        if title:
            prod['title'] = title[0].strip()

        img = is_empty(response.xpath(
            '//img[@itemprop="image"]/@data-zoom-image').extract())
        if img:
            prod['image_url'] = urlparse.urljoin(response.url, img)

        price = response.xpath(
            '//span[@itemprop="price"]/text()').re(FLOATING_POINT_RGEX)
        if price:
            prod['price'] = Price(price=price[0],
                                  priceCurrency='GBP')

        description = response.xpath(
            '//div[@class="product-description"]').extract()
        if not description:
            description = response.xpath(
                '//ul[@itemprop="description"]'
            ).extract()
        if description:
            prod['description'] = description[0].strip()

        brand = response.xpath(
            '//img[@itemprop="logo"]/@alt').extract()
        if brand:
            prod['brand'] = brand[0]

        if not prod.get('brand', None):
            dump_url_to_file(response.url)

        stock_status = is_empty(response.xpath(
            '//p[@itemprop="availability"]/@content').extract(), '')
        prod['is_out_of_stock'] = 'InStock' not in stock_status

        sku = is_empty(response.xpath(
            '//strong[@itemprop="sku"]/text()'
        ).extract())
        if sku:
            prod['sku'] = sku
            if self.POPULATE_REVIEWS:
                url = self.REVIEW_URL.format(sku=sku)
                meta = {'product': prod, 'handle_httpstatus_list': [404]}
                return Request(url, self.parse_buyer_reviews, meta=meta)

        return prod

    def parse_buyer_reviews(self, response):
        product = response.meta['product']
        try:
            js = json.loads(response.body_as_unicode()).get('reviews')
        except:
            return product

        num_of_reviews = re.search('"ratingCount": (\d+)', js)
        average_rating = re.search('"ratingValue": (\d+\.\d+)', js)

        if num_of_reviews and average_rating:
            buyer_reviews = BuyerReviews(
                int(num_of_reviews.group(1)),
                float(average_rating.group(1)),
                {})
            product['buyer_reviews'] = buyer_reviews
        else:
            product['buyer_reviews'] = ZERO_REVIEWS_VALUE

        return product
