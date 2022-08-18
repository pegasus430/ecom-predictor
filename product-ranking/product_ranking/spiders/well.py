from __future__ import division, absolute_import, unicode_literals

import string
import re

from scrapy.log import DEBUG, ERROR, WARNING

from product_ranking.items import SiteProductItem, RelatedProduct, Price, \
    BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set


class WellProductsSpider(BaseProductsSpider):
    name = 'well_products'
    allowed_domains = ["well.ca"]
    start_urls = []
    SEARCH_URL = "https://well.ca/searchresult.html?keyword={search_term}"

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        cond_set(
            product,
            'title',
            response.xpath('//h1[@class="productName"]/text()').extract(),
            string.strip
        )

        cond_set(
            product,
            'price',
            response.xpath('//div[@class="productPrice"]'
                           '/div[@itemprop="price"]/text()').extract(),
            self.__convert_to_price
        )

        if not product.get('price', None):
            self.log('Unknown currency at %s' % response.url, ERROR)

        cond_set(
            product,
            'brand',
            response.xpath(
                '//div[@class="view_all_products_button"]/a/text()'
            ).extract(),
            self.__parse_brand
        )

        cond_set(
            product,
            'image_url',
            response.xpath('//div[@class="product-image"]/img/@src').extract()
        )

        cond_set(
            product,
            'description',
            response.xpath('//div[@itemprop="description"]/text()').extract()
        )

        alsob_list = self.__make_list(
            response.xpath('//div[@id="similar_carousel"]/'
                           'div[@class="productBox"]')
        )

        related_list = self.__make_list(
            response.xpath('//div[@id="brand_carousel"]/'
                           'div[@class="carouselAdBox"]')
        )

        product['related_products'] = {
            "recommended": related_list,
            "also_bought": alsob_list,
        }

        product['locale'] = "en-CA"

        avg_rating = \
            response.xpath('//div[contains(@class, '
                           '"product_rating_number")]/text()').extract()
        if avg_rating:
            avg_rating = float(avg_rating[0].split('/')[0])
        else:
            self.log('AVG-Rating was not found.', WARNING)
            avg_rating = 0

        total_review = response.xpath('//span[@class="revtext"]/'
                                      'text()').extract()
        if total_review:
            total_review = re.findall(r'Rating\s?\((\d+)\s?Reviews',
                                      total_review[0])
        if not total_review:
            self.log('Total review was not found.', WARNING)
            total_review = 0
        else:
            total_review = int(total_review[0])

        product['buyer_reviews'] = BuyerReviews(
            num_of_reviews=total_review,
            average_rating=avg_rating,
            rating_by_star={}
        )

        return product

    @staticmethod
    def __convert_to_price(x):
        if not x.startswith('$'):
            return None
        return Price(
            priceCurrency='CAD',
            price=float(re.findall(r'(\d+\.?\d*)', x)[0])
        )

    @staticmethod
    def __parse_brand(x):
        return x.replace('View all products by ', '')

    def _scrape_total_matches(self, response):
        links = \
            response.xpath('//a[@class="product_grid_link"]/@href').extract()
        if not links:
            return 0
        total = response.xpath(
            "//div[@class='title']/h3/small"
            "/text()").re(r'\((\d+) Products\)')
        if total:
            return int(total[0])
        return 0

    @staticmethod
    def __make_list(rlist):
        prodlist = []
        for r in rlist:
            href = r.xpath('a[@class="product_grid_link"]'
                           '/@href').extract()[0]
            text = r.xpath('div/img/@alt').extract()[0]
            prodlist.append(RelatedProduct(text, href))
        return prodlist

    def _scrape_product_links(self, response):
        links = \
            response.xpath('//a[@class="product_grid_link"]/@href').extract()
        if not links:
            self.log("Found no product links.", DEBUG)
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        links = response.xpath(
            "//div[@class='main_search_result']/a[@id='next']/@href")
        lastnav = response.xpath(
            "//div[@class='gridNav']/a[contains(@class,'last')]/@href").extract()
        if lastnav:
            lastnav = lastnav[0]
        else:
            return
        if response.url == lastnav:
            return None
        next_page = None
        if links:
            next_page = links.extract()[0]
        return next_page
