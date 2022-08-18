from __future__ import division, absolute_import, unicode_literals

import re

from lxml import html
from scrapy.http import Request
from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value, \
    FLOATING_POINT_RGEX
from spiders_shared_code.ebay_variants import EbayVariants


class EbayProductsSpider(BaseProductsSpider):
    name = 'ebay_products'
    allowed_domains = ["ebay.com"]

    SEARCH_URL = 'https://www.ebay.com/sch/i.html?_from=R40&_trksid=p2380057.m570.l1313.TR0.TRC0.H0.X{search_term}.TRS0&_nkw={search_term}&_sacat=0'

    def __init__(self, *args, **kwargs):
        super(EbayProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)
        self.ev = EbayVariants()

    def start_requests(self):
        for request in super(EbayProductsSpider, self).start_requests():
            if not self.product_url:
                request = request.replace(callback=self._parse_search)
            yield request

    def _parse_search(self, response):
        prod_links = list(self._scrape_product_links(response))
        if prod_links:
            return self.parse(response)
        category_links = response.xpath('//section[contains(@class, "b-visualnav") '
                                        'and contains(div[@class="b-visualnav__heading"]/h2/text(), "Shop by Category")]'
                                        '//a/@href').extract()
        meta = response.meta.copy()
        meta['category_links'] = category_links[1:] if len(category_links) > 1 else None
        if category_links:
            return Request(
                category_links[0],
                meta=meta
            )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        desc = self._parse_description(response)
        cond_set_value(product, 'description', desc)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        if categories:
            cond_set_value(product, 'department', categories[-1])

        model = self._parse_model(response)
        cond_set_value(product, 'model', model)

        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc)

        product['locale'] = "en-US"

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        buyer_reviews = self._parse_buyer_reviews(response)
        cond_set_value(product, 'buyer_reviews', buyer_reviews)

        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//h1[@itemprop="name"]/text() | '
                               '//h1[@class="product-title"]/text()').extract()
        return title[0] if title else None

    def _parse_brand(self, response):
        brand = response.xpath('//*[@itemprop="brand"]/span/text()').extract()
        return brand[0] if brand else None

    @staticmethod
    def _parse_image(response):
        image_url = response.xpath('//img[@itemprop="image"]/@src |'
                                   '//img[contains(@class, "vi-image-gallery__image")]/@src').extract()
        return image_url[0] if image_url else None

    @staticmethod
    def _parse_description(response):
        description = response.xpath('//meta[@property="og:description"]/@content | '
                                     '//div[@class="item-desc"]//span[@class="cc-ts-ITALIC"]/text()').extract()
        return description[0] if description else None

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//ul[@itemtype="https://schema.org/BreadcrumbList"]'
                                    '//*[@itemprop="name"]/text() | '
                                    '//div[contains(@class, "breadcrumb")]/ol/li[not(@class="home")]/a/span/text()').extract()
        return categories

    @staticmethod
    def _parse_price(response):
        price = response.xpath('//span[@itemprop="price"]/@content | '
                               '//h2[@class="display-price"]/text()').re(FLOATING_POINT_RGEX)
        priceCurrency = response.xpath('//span[@itemprop="priceCurrency"]/@content').extract()
        if not priceCurrency:
            priceCurrency = re.findall(r'"priceCurrency":"(.*?)"', response.body)
        if price and priceCurrency:
            return Price(price=float(price[0].replace(',', '')), priceCurrency=priceCurrency[0])

    @staticmethod
    def _parse_upc(response):
        upc = response.xpath('//td[@class="attrLabels" and contains(text(), "UPC:")]'
                             '/following-sibling::td/h2[@itemprop="gtin13"]/text() |'
                             '//div[@class="s-name" and contains(text(), "UPC")]'
                             '/following-sibling::div[@class="s-value"]/text()').extract()
        if upc:
            upc = upc[0].split(',')
        return upc[0] if upc and upc[0] != 'Does not apply' else None

    @staticmethod
    def _parse_model(response):
        model = response.xpath("//div[@class='prodDetailSec']//tr//td[contains(., 'Model')]/text()").extract()
        if not model:
            model = response.xpath('//h2[@itemprop="model"]/text()').extract()
        return model[-1] if model else None

    @staticmethod
    def _parse_buyer_reviews(response):

        reviews_count = response.xpath('//div[@class="rating--details"]'
                                       '//span[@class="reviews--count"]/text() |'
                                       ' //span[@itemprop="reviewCount"]/@content').re('\d+')

        average_rating = response.xpath('//div[@class="rating--details"]//span[@class="review--start--rating"]/text()'
                                        '| //span[@itemprop="ratingValue"]/@content').re('^\d\.?\d*$')

        if reviews_count and average_rating:
            reviews_count = int(reviews_count[0])
            average_rating = float(average_rating[0])
            buyer_review_values = {
                'num_of_reviews': reviews_count,
                'average_rating': average_rating,
                'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
            }
            reviews = response.xpath('//div[@class="rating--details"]//li[@class="review--item"]//div[@class="reviews--item--bar--r"]/span/text()'
                                     '| //div[@id="rwid"]//ul[@class="ebay-review-list"]/li[@class="ebay-review-item"]//div[@class="ebay-review-item-r"]/span/text()').re('^\d+$')

            for idx, review in enumerate(reviews):
                buyer_review_values['rating_by_star'][str(5-idx)] = int(review)

            return BuyerReviews(**buyer_review_values)

    def _parse_variants(self, response):
        self.ev.setupSC(response)
        return self.ev._variants()

    def _scrape_total_matches(self, response):
        total_matches = response.xpath('//span[@class="rcnt" or @class="listingscnt"]/text()').re('\d{1,3}[,\d]*')
        total_matches = int(total_matches[0].replace(',', '')) if total_matches else None
        return total_matches

    def _scrape_product_links(self, response):
        links = response.xpath('//li[contains(@id, "item")]//h3/a/@href |'
                               '//ul[contains(@class, "b-list__items")]'
                               '//div[@class="s-item__image"]'
                               '/a/@href').extract()
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath(
            '//table[@id="Pagination"]//a[contains(@class, "next") and not(@aria-disabled)]/@href |'
            '//div[@class="b-pagination"]//a[@rel="next"]/@href'
        ).extract()
        meta = response.meta.copy()
        if next_page:
             return Request(
                 next_page[0],
                 meta=meta,
                 dont_filter=True
             )

        category_links = meta.get('category_links')
        if category_links:
            meta['category_links'] = category_links[1:] if len(category_links) > 1 else None
            return Request(
                category_links[0],
                meta=meta,
                dont_filter=True
            )

    def _get_products(self, response):
        for request in super(EbayProductsSpider, self)._get_products(response):
            yield request.replace(dont_filter=True)
