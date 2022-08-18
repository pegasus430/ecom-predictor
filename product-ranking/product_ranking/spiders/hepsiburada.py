# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback

from scrapy.log import WARNING

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, FLOATING_POINT_RGEX
from product_ranking.utils import is_empty
from spiders_shared_code.hepsiburada_variants import HepsiburadaVariants


class HepsiburadaProductsSpider(BaseProductsSpider):
    name = 'hepsiburada_products'
    allowed_domains = ["hepsiburada.com"]

    SEARCH_URL = "http://www.hepsiburada.com/ara?q={search_term}"

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        if not response.xpath(".//*[@itemtype='http://schema.org/Product']"):
            # not a product page
            product['no_longer_available'] = True
        else:
            product['description'] = is_empty(response.xpath('.//span[@itemprop="description"]/@content').extract())

            product['brand'] = is_empty(response.xpath('.//span[@class="brand-name"]/a/text()').extract())

            title = self._parse_title(response)
            product['title'] = title

            in_stock = re.search(r'"product_status":"InStock"', response.body)
            product['is_out_of_stock'] = not bool(in_stock)

            price = self._parse_price(response)
            product['price'] = price

            images = response.xpath('.//img[@itemprop="image" and contains(@class, "product-image")]')
            if images:
                if len(images) == 1:
                    product['image_url'] = images.xpath('@data-src|@src').extract()[0].strip('/')
                else:
                    images_height = [int(x) for x in images.xpath('@height').extract()]
                    product['image_url'] = images.xpath('@data-src|@src').extract()[
                        images_height.index(max(images_height))
                    ].strip('/')

            buyer_reviews = self._parse_buyer_reviews(response)
            product['buyer_reviews'] = buyer_reviews

            product['sku'] = is_empty(re.findall(r'"product_skus":\["(\w+)', response.body))
            product['reseller_id'] = product['sku']

            variants = self._parse_variants(response, product['sku'])
            product['variants'] = variants

            categories = self._parse_categories(response)
            product['categories'] = categories

            was_now = self._parse_was_now(response)
            product['was_now'] = was_now

            save_percent = self._parse_save_percent(response)
            product['save_percent'] = save_percent

            if any([was_now, save_percent]):
                product['promotions'] = True

            if categories:
                product['department'] = categories[-1]

            product['locale'] = "tr-TR"

        return product

    def _parse_title(self, response):
        title = is_empty(
            response.xpath('//*[contains(@class, "title-wrapper")]//span[@class="product-name"]/text()').extract())

        if not title:
            title = is_empty(response.xpath('.//h1[contains(@class, "product-name")]/text()').extract())

        return title

    def _parse_price(self, response):
        price = response.xpath('.//span[@itemprop="price"]/span[@data-bind]/text()').extract()
        if price:
            try:
                price = [re.search(
                    r'\d*\.\d+|\d+',
                    '.'.join(map(lambda x: x.replace(".", ""), price))
                ).group(0)]
            except:
                self.log(traceback.format_exc())

        if not price:
            price = response.xpath('//*[@id="offering-price"]/@content').re(FLOATING_POINT_RGEX)

        if price:
            return Price(
                priceCurrency=is_empty(response.xpath('.//span[@itemprop="priceCurrency"]/@content').extract(),
                                       'TRY'),
                price=price[0]
            )

    @staticmethod
    def _parse_price(response):
        price = response.xpath('.//span[@itemprop="price"]/@content').re(FLOATING_POINT_RGEX)
        if price:
            price = float(price[0])
            return Price(priceCurrency='TRY', price=price)

    def _parse_variants(self, response, sku):
        hv = HepsiburadaVariants()
        product_json = re.search('var productModel = (.*?)};', response.body_as_unicode())
        try:
            product_json = json.loads(product_json.group(1) + '}')
            product_json = product_json.get('product', {}).get('variants', [])
            if product_json:
                hv.setupSC(product_json, sku)
                return hv._variants()
        except:
            self.log('Error Parsing Variants: {}'.format(traceback.format_exc()), WARNING)


    @staticmethod
    def _parse_buyer_reviews(response):
        buyer_reviews = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        average_rating = response.xpath('//span[@class="ratings"]//span[@itemprop="ratingValue"]/@content').re('\d,?\d*]?')
        rating_count = response.xpath('//span[@itemprop="reviewCount"]/@content').re('\d+')
        if average_rating and rating_count:
            buyer_reviews['average_rating'] = float(average_rating[0].replace(',', '.'))
            buyer_reviews['num_of_reviews'] = int(rating_count[0])
            reviews = response.xpath('//span[@class="rating-count"]').re('\d+')
            for idx, review in enumerate(reviews):
                buyer_reviews['rating_by_star'][str(5-idx)] = int(review)
            return BuyerReviews(**buyer_reviews)

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//li[@itemtype="http://data-vocabulary.org/Breadcrumb"]'
                                    '//span[@itemprop="title"]/text()').extract()
        return categories

    def _parse_was_now(self, response):
        old_price = response.xpath('//del[@id="originalPrice"]/text()').re('\d{1,3}[,\.\d{3}]*,?\d*')
        current_price = self._parse_price(response)
        if old_price and current_price:
            try:
                old_price = old_price[0].replace('.', '').replace(',', '.')
                return ', '.join([str(current_price.price), old_price])
            except:
                self.log('Error Parsing Was_now: {}'.format(traceback.format_exc()), WARNING)

    @staticmethod
    def _parse_save_percent(response):
        save_percent = response.xpath('//span[@class="discount-amount"]/span/text()').re(FLOATING_POINT_RGEX)
        return float(save_percent[0]) if save_percent else None

    def _get_products(self, response):
        for request in super(HepsiburadaProductsSpider, self)._get_products(response):
            yield request.replace(dont_filter=True)

    def _scrape_total_matches(self, response):
        num_results = response.xpath(".//*[@class='result-count']/text()").re('\d+')

        if num_results:
            return int(num_results[0].replace(".", ""))

        self.log("Failed to parse total number of matches.", level=WARNING)

        return None

    def _scrape_product_links(self, response):
        links = response.xpath(".//*[contains(@class,'product-list')]//a[@data-bind]/@href").extract()

        if not links:
            self.log("Found no product links.", WARNING)

        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath(".//*[@id='pagination']//*[a[contains(@class,'active')]]"
                                   "/following-sibling::*[1]/a/@href").extract()
        if next_page:
            return next_page[0]

        return None
