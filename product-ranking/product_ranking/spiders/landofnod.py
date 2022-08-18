# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import re
import json
from urlparse import urljoin
from datetime import datetime

from product_ranking.items import SiteProductItem, RelatedProduct, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set, cond_set_value
from product_ranking.utils import is_empty

from scrapy import Request
from scrapy.log import WARNING, ERROR


class LandOfNodProductsSpider(BaseProductsSpider):
    name = 'landofnod_products'
    allowed_domains = ["www.landofnod.com"]
    use_proxies = False
    handle_httpstatus_list = [404]

    SEARCH_URL = 'http://www.landofnod.com/search?query={search_term}'

    REVIEWS_URL = 'http://api.bazaarvoice.com/data/reviews.json' \
                  '?passkey=q12j4skivgb89bci049b3pwua' \
                  '&apiversion=5.4' \
                  '&Include=Products' \
                  '&Stats=Reviews' \
                  '&Limit=1' \
                  '&Filter=ProductId:{product_id}'

    def _scrape_total_matches(self, response):
        total_matches = response.xpath("//*[@id='_productMatch' or contains(@class,'product-match')]"
                                       "/text()[normalize-space()]").re('\d+')
        if total_matches:
            return int(total_matches[0])

        total_matches = response.xpath(".//*[contains(@class,'jsItemRow')]")
        if total_matches:
            return len(total_matches)

        return None

    def _scrape_product_links(self, response):
        products = response.xpath(".//*[contains(@class,'jsItemRow')]")

        for product in products:
            link = product.xpath(".//a/@href").extract()
            if link:
                yield link[0], SiteProductItem()

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        if self._parse_no_longer_available(response) or response.status in self.handle_httpstatus_list:
            cond_set_value(product, 'no_longer_available', True)

            yield product
        else:
            cond_set_value(product, 'no_longer_available', False)

            product_data = self._parse_product_data(response)

            cond_set_value(product, 'title', self._parse_title(response, product_data))
            cond_set_value(product, 'sku', self._parse_sku(response, product_data))
            cond_set_value(product, 'image_url', self._parse_image_url(response, product_data))
            cond_set_value(product, 'price', self._parse_price(response, product_data))

            cond_set_value(product, 'price_original', self._parse_price_original(response))
            cond_set_value(product, 'locale', self._parse_locale(response))
            cond_set_value(product, 'reseller_id', self._parse_reseller_id(response))

            cond_set_value(product, 'description', self._parse_description(response))

            categories = self._parse_categories(response)
            if categories:
                cond_set_value(product, 'categories', categories)
                cond_set_value(product, 'category', categories[-1])

            cond_set_value(product, 'is_out_of_stock', self._parse_is_out_of_stock(response))

            cond_set_value(product, 'related_products', self._parse_related_products(response))

            if product.get('sku'):
                product_id = 's{}'.format(product.get('sku'))
            else:
                product_id = product.get('reseller_id')

            yield Request(self.REVIEWS_URL.format(product_id=product_id),
                          callback=self._parse_buyer_reviews,
                          meta=response.meta,
                          dont_filter=True)

    def _parse_no_longer_available(self, response):
        message_404 = response.xpath(".//*[contains(@class,'error404')]")

        return bool(message_404)

    def _parse_product_data(self, response):
        try:
            product_data = response.xpath("..//script[@type='application/ld+json']/text()").extract()
            if product_data:
                return json.loads(product_data[0])
        except Exception as e:
            self.log(str(e), ERROR)

        return None

    def _parse_title(self, response, product_data=None):
        if product_data and product_data.get('name'):
            return product_data.get('name')

        title = response.xpath(".//*[@class='productTitleText']/text()").extract()
        if title:
            return title[0].strip()

        return None

    def _parse_sku(self, response, product_data=None):
        if product_data and product_data.get('sku'):
            return product_data.get('sku')

        sku = response.xpath(".//*[@id='_skuNum']/text()").extract()
        if sku:
            return sku[0].strip()

        return None

    def _parse_image_url(self, response, product_data=None):
        if product_data and product_data.get('image'):
            return 'http:{}'.format(product_data.get('image'))

        image = response.xpath(".//*[@id='_imgLarge']/@src").extract()
        if image:
            return image[0]

        return None

    def _parse_price(self, response, product_data=None):
        currency = is_empty(
            response.xpath(
                ".//meta[@id='_fbCurrency' or "
                "@property='og:price:currency']/@content"
            ).extract()
        )

        if product_data and product_data.get('offers'):
            offer = product_data.get('offers')
            offer_type = offer.get('@type')
            offer_currency = offer.get('priceCurrency')

            if currency and offer_currency != currency:
                self.log('Different currencies detected: {} != {}'.format(offer_currency, currency), WARNING)
                offer_currency = currency

            if offer_type == 'Offer':
                return Price(offer_currency, offer.get('price'))
            if offer_type == 'AggregateOffer':
                return Price(offer_currency, offer.get('lowPrice'))

        price = response.xpath(".//meta[@id='_fbPrice']/@content").extract()
        if price:
            price_parts = price[0].split('-')[0].strip().split(' ')

            if len(price_parts) > 1:
                currency = price_parts[0]
                price = price_parts[1]
            else:
                currency = 'USD'
                price = price_parts[0]

            return Price(currency, price)

        return None

    def _parse_price_original(self, response):
        price = response.xpath(".//meta[@id='_fbStandardPrice']/@content").extract()
        if price:
            price_parts = price[0].split('-')[0].strip().split(' ')

            if len(price_parts) > 1:
                currency = price_parts[0]
                price = price_parts[1]
            else:
                currency = 'USD'
                price = price_parts[0]

            return Price(currency, price)

        return None

    def _parse_locale(self, response):
        locale = response.xpath("*//meta[@http-equiv='content-language']/@content").extract()
        if locale:
            return locale[0]

        return None

    def _parse_reseller_id(self, response):
        reseller_id = re.search(r'/[fs](\d+)$', response.url)
        if reseller_id:
            return reseller_id.group(1)

        return None

    def _parse_description(self, response):
        description = response.xpath(
            ".//*[@class='overviewPrintContainer']/div[contains(@class,'overviewPrint')]"
        ).extract()

        if description:
            return ''.join(map(lambda x: re.sub(r'[\r\n]', '', x), description[:-1]))  # exclude Knock Knock Jokes
        description = is_empty(
            response.xpath('//*[@data-desc]/@data-desc').extract()
        )

        return description

    def _parse_categories(self, response):
        try:
            breadcrumbs_data = response.xpath(
                ".//div[@class='breadcrumbsInnerWrap']/script[@type='application/ld+json']/text()"
            ).extract()
            if breadcrumbs_data:
                breadcrumbs_data = json.loads(breadcrumbs_data[0])
                return [x.get('item', {}).get('name', {}) for x in breadcrumbs_data.get('itemListElement', {})]
        except Exception as e:
            self.log(str(e), WARNING)

        breadcrumbs = response.xpath(".//div[@class='breadcrumbsInnerWrap']//a/text()").extract()
        if breadcrumbs:
            return breadcrumbs

        breadcrumbs = response.xpath(
            '//*[contains(@class, "breadcrumb-list-item")]/a/text()').extract()
        if breadcrumbs:
            return breadcrumbs[:-1]

        return None

    def _parse_is_out_of_stock(self, response):
        stock = is_empty(
            response.xpath(
                ".//meta[@id='_fbAvail' or "
                "@property='og:availability']/@content"
           ).extract()
        )
        if not stock:
            return None

        return False if 'InStock' in stock else True

    def _parse_related_products(self, response):
        products = dict()

        product_items = map(
            lambda x: RelatedProduct(x.xpath(".//span[@class='productName']/text() | text()[normalize-space()]").extract()[0],
                                     urljoin(response.url, x.xpath("@href").extract()[0])),
            response.xpath(".//*[@id='productItems']"
                           "//a[contains(@id,'__itemTitleLink') or contains(@id,'__productNameLink')]"))
        if product_items:
            products['product_items'] = product_items

        designers_recommend = map(
            lambda x: RelatedProduct(x.xpath("@title").extract()[0],
                                     urljoin(response.url, x.xpath("@href").extract()[0])),
            response.xpath(".//*[@id='coordinatingItems']//a[@id='_lnkImage']"))
        if designers_recommend:
            products['designers_recommend'] = designers_recommend

        return products if products else None

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']

        try:
            data = json.loads(response.body)

            product_data = data.get('Includes', {}).get('Products', {})
            if product_data:
                review_statistics = product_data.values()[0].get('ReviewStatistics')

                if review_statistics:
                    cond_set_value(product, 'buyer_reviews', BuyerReviews(
                        num_of_reviews=review_statistics.get('TotalReviewCount', 0),
                        average_rating=round(review_statistics.get('AverageOverallRating', 0), 1),
                        rating_by_star=dict(map(lambda x: (str(x['RatingValue']), x['Count']),
                                                review_statistics.get('RatingDistribution')))
                    ))

                    if review_statistics.get('LastSubmissionTime'):
                        last_buyer_review_date = review_statistics.get('LastSubmissionTime').split('.')[0]
                        cond_set_value(product,
                                       'last_buyer_review_date',
                                       datetime.strptime(last_buyer_review_date,
                                                         "%Y-%m-%dT%H:%M:%S").strftime('%d-%m-%Y'))
        except Exception as e:
            self.log(str(e), WARNING)

        yield product

    def _scrape_results_per_page(self, response):
        # landofnod.com does not support pagination
        return None

    def _scrape_next_results_page_link(self, response):
        # landofnod.com does not support pagination
        return None
