from __future__ import division, absolute_import, unicode_literals

import re
import string

from scrapy.log import WARNING

from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults,\
    cond_set_value

is_empty = lambda x, y=None: x[0] if x else y

class BabymonitorsdirectProductsSpider(BaseProductsSpider):
    """Spider for babymonitorsdirect.co.uk.

    scrapy crawl babymonitorsdirectcouk_products
    -a searchterms_str="baby monitor" [-a order=pricedesc]

    Note: some product where price market as 'DISCONTNUED' may
    be out of correct position during price order search.
    Note: This type of spider need first to crawl through all
    pagination page to count total_matches.
    """
    name = 'babymonitorsdirectcouk_products'
    allowed_domains = ["babymonitorsdirect.co.uk"]
    SEARCH_URL = "http://www.babymonitorsdirect.co.uk/catalogsearch/" \
                 "result/index/?dir={sort}&order={order}&q={search_term}"

    SEARCH_SORT = {
        'ASC': 'asc',
        'DESC': 'desc'
    }

    SEARCH_ORDER = {
        'relevance': 'relevance',
        'name': 'name',
        'price': 'price'
    }

    def __init__(self, order='relevance', *args, **kwargs):
        order = self.SEARCH_ORDER.get(order, 'relevance')
        formatter = FormatterWithDefaults(order=order, sort='asc')
        super(BabymonitorsdirectProductsSpider,
              self).__init__(formatter, *args, **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        # Set locale
        cond_set_value(product, 'locale', 'en_GB')

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse reseller_id
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id, conv=string.strip)

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse special pricing
        special_pricing = self._parse_special_pricing(response)
        cond_set_value(product, 'special_pricing', special_pricing, conv=bool)

        # Parse stock status
        is_out_of_stock = self._parse_stock_status(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        # Parse related products
        # related_products = self._parse_related_products(response)
        # cond_set_value(product, 'related_products', related_products)

        # Parse buyer reviews
        # buyer_reviews = self._parse_buyer_reviews(response)
        # cond_set_value(product, 'buyer_reviews', buyer_reviews)

        return product

    def _parse_reseller_id(self, response):
        reseller_id = is_empty(response.xpath('.//*[@class="sku"]//span[@class="value"]/text()').extract())
        if reseller_id:
            reseller_id = reseller_id.strip()
        return reseller_id

    def _parse_title(self, response):
        title = is_empty(
            response.xpath(
                '//div[@class="BlockContent"]/'
                'h1/text() |'
                '//h1[@itemprop="name"]/text()').extract()
        )
        if title:
            title = title.strip()

        return title

    def _parse_brand(self, response):
        brand = is_empty(
            response.xpath(
                '//div[@class="DetailRow"]/div[contains(text(), "Brand:")]'
                '/../div[@class="Value"]/a/text() |'
                '//meta[@itemprop="brand"]/@content'
            ).extract()
        )

        return brand

    def _parse_price(self, response):
        price = is_empty(
            response.xpath('//p[@class="special-price"]/span[@itemprop="price"]/text()'
                           ' |//span[@class="regular-price"]/span[@itemprop="price"]/text()').extract(), 0.00
        )
        if price:
            price = is_empty(
                re.findall(
                    r'(\d+\.\d+)',
                    price
                )
            )

        return Price(
            price=price,
            priceCurrency='GBP'
        )

    def _parse_special_pricing(self, response):
        special_pricing = is_empty(
            response.xpath(
                '//*[@class="old-price"]/span[@class="price"]'
                '/text()'
            ), False
        )

        return special_pricing

    def _parse_stock_status(self, response):
        is_out_of_stock = is_empty(
            response.xpath(
                '//div[@class="DetailRow"]/div[contains(text(), "Availability:")]'
                '/../div[@class="Value"]/text() |'
                '//div[@class="CurrentlySoldOut"]/p[1]/text() |'
                '//p[contains(@class, "availability")]/span/text()'
            ).extract(), ''
        )

        is_out_of_stock = "in stock" not in is_out_of_stock.lower()

        return is_out_of_stock

    def _parse_image_url(self, response):
        image_url = is_empty(
            response.xpath(
                '//img[@id="image-main"]/@src'
            ).extract()
        )

        return image_url

    def _parse_description(self, response):
        description = is_empty(
            response.xpath(
                '//div[contains(@class,"box-description")]'
            ).extract()
        )

        return description

    # def _parse_related_products(self, response):
    #     related_products = []
    #
    #     for prod in response.xpath('//ul[@class="ProductList"]/li'):
    #         prod_all = prod.xpath('div[@class="ProductDetails"]/strong/a')
    #         title = prod_all.xpath('text()').extract()
    #         url = prod_all.xpath('@href').extract()
    #         if title:
    #             title = title[0]
    #         if url:
    #             url = url[0]
    #         related_products.append(RelatedProduct(title, url))
    #
    #     return related_products

    # def _parse_buyer_reviews(self, response):
    #     num_of_reviews = response.xpath(
    #         '//div[@class="DetailRow"]/div[contains(text(), "Rating:")]'
    #         '/../div[@class="Value"]/span/a/text()'
    #     ).extract()
    #
    #     if num_of_reviews:
    #         num_of_reviews = re.findall("\d+", num_of_reviews[0])
    #         if num_of_reviews:
    #             num_of_reviews = int(num_of_reviews[0])
    #         if not num_of_reviews:
    #             num_of_reviews = None
    #
    #     average_rating = response.xpath(
    #         '//div[@class="DetailRow"]/div[contains(text(), "Rating:")]'
    #         '/../div[@class="Value"]/img/@src'
    #     ).extract()
    #     if average_rating:
    #         average_rating = int(re.findall("IcoRating(\d)",
    #                              average_rating[0])[0])
    #     if not average_rating:
    #         average_rating = 0
    #         num_of_reviews = 0
    #
    #     buyer_reviews = BuyerReviews(num_of_reviews=int(num_of_reviews),
    #                                  average_rating=float(average_rating),
    #                                  rating_by_star={1: 0, 2: 0, 3: 0,
    #                                                  4: 0, 5: 0})
    #     if average_rating or num_of_reviews:
    #         cond_set_value(product, 'buyer_reviews', buyer_reviews)
    #         new_meta = response.meta.copy()
    #         new_meta['product'] = product
    #         return Request(url=response.url,
    #                        meta=new_meta,
    #                        callback=self._extract_reviews,
    #                        dont_filter=True)
    #     else:
    #         buyer_reviews = ZERO_REVIEWS_VALUE
    #
    #     return buyer_reviews
    #
    # def _extract_reviews(self, response):
    #     product = response.meta['product']
    #     num, avg, by_star = product.get('buyer_reviews')
    #
    #     stars = response.xpath('//ol[@class="ProductReviewList"]/'
    #                            'li/h4/img/@src').re('IcoRating(\d)')
    #
    #     for i in stars:
    #         by_star[int(i)] += 1
    #
    #     buyer_reviews = BuyerReviews(num_of_reviews=num,
    #                                  average_rating=avg,
    #                                  rating_by_star=by_star)
    #
    #     cond_set_value(product, 'buyer_reviews', buyer_reviews)
    #     next_page = response.xpath('//p[@class="ProductReviewPaging"]/span'
    #                                '/a[contains(text(),"Next")]/@href')\
    #         .extract()
    #
    #     if next_page:
    #         new_meta = response.meta.copy()
    #         new_meta['product'] = product
    #         return Request(url=next_page[1], meta=new_meta,
    #                        callback=self._extract_reviews,
    #                        dont_filter=True)
    #     else:
    #         return product

    def _scrape_total_matches(self, response):
        if 'No products found' in \
                response.body_as_unicode():
            total_matches = 0
        else:
            total_matches = is_empty(
                response.xpath('//div[@class="sorter"]'
                               '/p[@class="amount"]'
                               '/text()').extract(), 0
            )
            if total_matches:
                total_matches = is_empty(
                    re.findall(
                        r'of (\d+) total',
                        total_matches
                    ), 0
                )

        return int(total_matches)

    def _scrape_results_per_page(self, response):
        num = is_empty(
            response.xpath('//div[@class="limiter"]'
                           '/select/option[@selected="selected"]'
                           '/text()').extract(), '0'
        )
        num = num.strip()

        return int(num)

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//ul[contains(@class, "products-grid")]/li[@class="item"]'
            '/h2[@class="product-name"]/a/@href').extract()
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        link = is_empty(
            response.xpath('//div[@class="pages"]/./'
                           '/li[@class="next"]/a/@href').extract()
        )

        if link:
            return link
        else:
            self.log('Unable to find next page link', WARNING)
            return None
