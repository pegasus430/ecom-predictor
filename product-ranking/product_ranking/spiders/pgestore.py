from __future__ import division, absolute_import, unicode_literals

import urllib

from scrapy.http import Request
from scrapy.log import ERROR, INFO, WARNING

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import (BaseProductsSpider, FormatterWithDefaults,
                                     cond_set_value)
from product_ranking.utils import is_empty


class PGShopProductSpider(BaseProductsSpider):
    name = 'pgestore_products'
    allowed_domains = ["pgshop.com", "pgestore.recs.igodigital.com"]

    SEARCH_URL = "http://www.pgshop.com/pgshop/" \
                 "?prefn1=showOnShop" \
                 "&q={search_term}&start={start}&sz=40" \
                 "&action=sort&srule={search_sort}" \
                 "&prefv1=1|2&appendto=0&pindex=3&ptype=ajax"

    SEARCH_SORT = {
        'product_name_ascending': 'A-Z',
        'product_name_descending': 'Z-A',
        'high_price': 'price-high-to-low',
        'low_price': 'price-low-to-high',
        'best_sellers': 'top-sellers',
        'rating': 'top rated',
        'default': 'default sorting rule',
    }

    def __init__(self, search_sort='default', *args, **kwargs):
        # All this is to set the site_name since we have several
        # allowed_domains.
        super(PGShopProductSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                search_sort=self.SEARCH_SORT[search_sort],
                start=0,
            ),
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        num_results = response.xpath(
            '//span[@class="number-copy"]/text()').extract()
        if num_results and num_results[0]:
            return int(num_results[0])
        else:
            no_result_div = response.xpath(
                '//div[@class="nosearchresult_div"]')
            if no_result_div:
                self.log("There is no result for this search term.", level=INFO)
                return 0
            else:
                return None

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//li[contains(@class, 'product-tile')]"
            "//p[@class='product-name']"
            "/a[contains(@class, 'name-link')]/@href").extract()
        if not links:
            if not response.xpath('//div[@class="nosearchresult_div"]'):
                self.log("Found no product links.", WARNING)
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        total_matches = response.meta.get('total_matches')
        start = response.meta.get('start', 0)

        if total_matches <= start or total_matches <= 40:
            return None

        start += 40
        if start > total_matches:
            start = total_matches
        response.meta['start'] = start

        search_term = response.meta.get('search_term')
        return self.url_formatter.format(
            self.SEARCH_URL,
            search_term=urllib.quote_plus(search_term.encode('utf-8')),
            start=start)

    def parse_product(self, response):
        prod = response.meta['product']
        prod['url'] = response.url
        prod['locale'] = 'en-US'

        title = response.xpath(
            '//*[@itemprop="name"]/text()').extract()
        if title:
            prod['title'] = title[0].strip()

        upc = response.xpath(
            '//*[@itemprop="gtin14"]/text()').extract()
        if upc:
            prod['upc'] = upc[0].strip()

        img = is_empty(response.xpath(
            '//div[contains(@class, "x1-target")]/img/@src').extract())
        if img:
            prod['image_url'] = img.split('?')[0]

        price = response.xpath('//section[contains(@class, "price")]'
                               '//span[contains(@class,"price-sales")'
                               ' or contains(@class,"price-nosale")]'
                               '/text()').extract()
        if price:
            prod['price'] = price[0].strip()

        description = response.xpath(
            'string(//div[contains(@class,"accordion-content")])').extract()
        if description:
            prod['description'] = description[0].strip()

        brand = response.xpath(
            '//a[@class="cta"]/@title').re('Visit the (\w+) brand shop')
        if brand:
            prod['brand'] = brand[0]

        stock_status = is_empty(response.xpath(
            '//button[@id="add-to-cart"]/text()').extract())
        if stock_status:
            is_out_of_stock = 'Out of Stock' in stock_status
            cond_set_value(prod, 'is_out_of_stock', is_out_of_stock)

        num_of_reviews = is_empty(
            response.xpath(
                '//*[@itemprop="ratingCount"]/text()'
            ).re('(\d+)')
        )
        average_rating = is_empty(
            response.xpath(
                '//*[@itemprop="ratingValue"]/text()'
            ).re('([\d.]+)')
        )

        if num_of_reviews and average_rating:
            buyer_reviews = BuyerReviews(
                num_of_reviews=int(num_of_reviews),
                average_rating=float(average_rating),
                rating_by_star={},
            )
            cond_set_value(prod, 'buyer_reviews', buyer_reviews)

        self._unify_price(prod)

        return prod

    def _unify_price(self, product):
        price = product.get('price')
        if price is None:
            return
        is_usd = not price.find('$')
        price = price[1:].replace(',', '')
        if is_usd and price.replace('.', '').isdigit():
            product['price'] = Price('USD', price)
