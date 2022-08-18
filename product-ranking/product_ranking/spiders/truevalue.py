# coding=utf-8
from __future__ import absolute_import, division, unicode_literals

import re
from urlparse import urljoin
from scrapy.log import INFO
from scrapy.conf import settings

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import BuyerReviews, SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator
from scrapy import Request


class TruevalueProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'truevalue_products'
    allowed_domains = ["truevalue.com"]

    SEARCH_URL = "http://www.truevalue.com/catalogsearch/result/?q={search_term}"
    REVIEWS_URL = "http://api.bazaarvoice.com/data/reviews.json?apiversion=5.5&passkey=p5zfp3g4eesutulj5jftp1i68&" \
                  "Filter=ProductId:{product_id}&Include=Products&Stats=Reviews"
    current_page = 1

    def __init__(self, *args, **kwargs):
        super(TruevalueProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        self.br = BuyerReviewsBazaarApi()

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def parse(self, response):
        if "productId=" in response.url:
            prod = SiteProductItem()
            prod['url'] = response.url
            prod['search_term'] = response.meta['search_term']
            prod['total_matches'] = 1
            prod['results_per_page'] = 1
            prod['search_redirected_to_product'] = True
            prod['ranking'] = 1
            response.meta['product'] = prod
            return self.parse_product(response)
        else:
            return super(TruevalueProductsSpider, self).parse(response)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse category
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse product id
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse model
        model = self._parse_model(response)
        cond_set_value(product, 'model', model)

        # Parse reviews
        if reseller_id:
            new_meta = {}
            new_meta['product'] = product
            new_meta['product_id'] = reseller_id
            return Request(self.REVIEWS_URL.format(product_id=reseller_id),
                           dont_filter=True,
                           callback=self._parse_buyer_reviews,
                           meta=new_meta)
        return product

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = response.xpath('//div[@itemprop="sku"]/text()').extract()
        if reseller_id:
            return reseller_id[0]

    @staticmethod
    def _parse_model(response):
        model = response.xpath('//*[contains(@class, "model-number")]/div[@class="value"]/text()').extract()
        if model:
            return model[0]

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//*[@itemprop="name"]/text()').extract()
        if title:
            return title[0].strip()

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//div[contains(@class, "brand")]/div[@class="value"]/text()').extract()
        if brand:
            return brand[0].strip()

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//div[contains(@class, "crumb")]//a/text()').extract()
        if categories:
            return categories[1:]

    @staticmethod
    def _parse_price(response):
        currency = "USD"
        price = response.xpath('//*[@class="price"]/text()').re(FLOATING_POINT_RGEX)
        try:
            price = float(price[0].replace(',', ''))
        except:
            price = 0
        return Price(price=price, priceCurrency=currency)

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath('//*[@property="og:image"]/@content').extract()
        if image_url:
            return image_url[0]

    def _parse_buyer_reviews(self, response):
        buyer_reviews = self.br.parse_buyer_reviews_single_product_json(response)
        product = response.meta['product']
        product['buyer_reviews'] = BuyerReviews(**buyer_reviews)
        return product

    def _scrape_total_matches(self, response):
        totals = re.search('"resultCount":(.*?),', response.body_as_unicode())
        return int(totals.group(1)) if totals else 0

    def _scrape_product_links(self, response):
        items = response.xpath('//ol[contains(@class, "product-items")]/li'
                               '//div[contains(@class, "product-item-details")]//a/@href').extract()
        if items:
            for item in items:
                item = urljoin(response.url, item)
                res_item = SiteProductItem()
                yield item, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath('//li[contains(@class, "pages-item-next")]/a/@href').extract()
        if next_page:
            next_page = urljoin(response.url, next_page[0])
            return next_page
