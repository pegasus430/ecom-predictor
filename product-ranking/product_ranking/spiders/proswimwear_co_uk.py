# -*- coding: utf-8 -*-

# TODO:
# 1) sorting options
# 2) buyer reviews
# 3) all the other fields that exist at the website


from __future__ import division, absolute_import, unicode_literals

import re

from scrapy.log import WARNING

from product_ranking.items import SiteProductItem, Price, BuyerReviews, \
    RelatedProduct
from product_ranking.spiders import (BaseProductsSpider, FormatterWithDefaults,
                                     cond_set, cond_set_value, 
                                     FLOATING_POINT_RGEX)

is_empty = lambda x,y=None: x[0] if x else y

class ProswimwearCoUkSpider(BaseProductsSpider):
    name = 'proswimwear_co_uk_products'
    allowed_domains = ["proswimwear.co.uk"]
    start_urls = []

    SEARCH_URL = ('http://www.proswimwear.co.uk/catalogsearch/result/'
                  '?category=&q={search_term}&dir=asc&order={sort_mode}')

    SORT_MODES = {
        'default': 'relevance',
        'relevance': 'relevance',
        'name': 'name',
        'price': 'price'
    }

    def __init__(self, order="default", *args, **kwargs):
        sort_mode = self.SORT_MODES.get(order)
        if sort_mode is None:
            raise Exception('%s sorting mode is not defined' % order)
        formatter = FormatterWithDefaults(sort_mode=sort_mode)
        super(ProswimwearCoUkSpider, self).__init__(formatter, *args, **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//h2[contains(@class, "product-name")]//a/@href').extract()
        for link in links:            
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next = response.xpath(
            '//li[contains(@class, "next")]'
            '//a[contains(@class, "next")]/@href'
        ).extract()
        return next[0] if next else None

    def _scrape_total_matches(self, response):
        totals = response.css('.sorter .amount ::text').extract()
        if not totals:
            self.log(
                "'total matches' string not found at %s" % response.url,
                WARNING
            )
            return
        total = totals[0]
        if 'total' in total.lower():  # like " Items 1 to 20 of 963 total "
            total = total.split('of ', 1)[1]
        total = re.search(r'([\d,\. ]+)', total)
        if not total:
            total = is_empty(response.xpath(
                "//p[contains(@class, 'amount')]/strong/text()"
            ).re(FLOATING_POINT_RGEX))
            if total:
                return int(total)
        if not total:
            self.log(
                "'total matches' string not found at %s" % response.url,
                WARNING
            )
            return
        total = total.group(1).strip().replace(',', '').replace('.', '')
        if not total.isdigit():
            self.log(
                "'total matches' string not found at %s" % response.url,
                WARNING
            )
            return
        total = int(total)
        self.total_results = total  # remember num of results
        return total

    def parse_product(self, response):
        product = response.meta['product']
        cond_set_value(product, 'locale', 'en-GB')

        title = response.css('.product-name h1').extract()
        cond_set(product, 'title', title)

        image_url = response.css('#zoom1 img::attr(src)').extract()
        cond_set(product, 'image_url', image_url)

        brand = response.css('.box-brand a img::attr(alt)').extract()
        cond_set(product, 'brand', brand)

        model = response.xpath('//div[@itemprop="name"]/p/text()').extract()
        cond_set(product, 'model', model)

        reseller_id = response.xpath('//*[@class="product-sku"]/text()').extract()
        cond_set(product, 'reseller_id', reseller_id)

        # Is_out_of_stock
        xpath = '//span[@id="availability-box" and text()="Out of stock"]'
        cond_set_value(product, 'is_out_of_stock', response.xpath(xpath), bool)

        # Description
        selection = response.css('.tabs-panels .std .content-wrapper')
        if selection:
            selection = selection[0].xpath('node()[normalize-space()]')
            cond_set_value(product, 'description', selection.extract(),
                           u''.join)

        # Price
        price = response.css('[itemprop=price]::attr(content)')
        currency = response.css('[itemprop=priceCurrency]::attr(content)')
        if price and float(price[0].extract()) and currency:
            cond_set_value(product, 'price', Price(price=price[0].extract(),
                                                   priceCurrency=currency[
                                                       0].extract()))

        self._populate_buyer_reviews(response, product)
        self._populate_related_products(response, product)

        return product

    def _populate_buyer_reviews(self, response, product):
        css = '#customer-reviews .rating::attr(style)'
        values = response.css(css).re('width:(\d+)')
        if not values:
            return
        values = [int(value) / 20 for value in values]
        total = len(values)
        avg = sum(values) / total
        by_star = {int(value): int(values.count(value)) for value in values}
        cond_set_value(product, 'buyer_reviews',
                       BuyerReviews(num_of_reviews=total, average_rating=avg,
                                    rating_by_star=by_star))

    def _populate_related_products(self, response, product):
        result = {}
        for section in response.css('.box-additional'):
            relation = section.css('.section-title::text').extract()
            if not relation or not relation[0].strip():
                continue
            relation = relation[0].strip()
            links = section.css('.item .product-name a')
            products = [RelatedProduct(title=lnk.css('::text')[0].extract(),
                                       url=lnk.css('::attr(href)')[
                                           0].extract().split('?')[0])
                        for lnk in links]
            if products:
                result[relation] = products
        cond_set_value(product, 'related_products', result or None)