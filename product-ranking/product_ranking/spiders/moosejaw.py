# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import re
import json
import urlparse
import traceback

from scrapy import Request
from scrapy.log import WARNING
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults, \
    cond_set, cond_set_value
from product_ranking.items import Price, SiteProductItem, BuyerReviews


class MoosejawProductsSpider(BaseProductsSpider):
    name = 'moosejaw_products'
    allowed_domains = ["moosejaw.com"]

    SEARCH_URL = "https://www.moosejaw.com/moosejaw/shop/SearchDisplay?searchTerm={search_term}" \
                 "&categoryId=&cmCat=-10020&storeId=10208&catalogId=10000001" \
                 "&langId=-1&pageSize=48&beginIndex=0"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?passkey=llqzkbnfdrdrj79t4ci66vkeh&apiversion=5.5" \
                 "&displaycode=18209-en_us&resource.q0=products&filter.q0=id:eq:{product_id}&stats.q0=questions,reviews" \
                 "&filteredstats.q0=questions,reviews&filter_questions.q0=contentlocale:eq:en_CA,en_US" \
                 "&filter_answers.q0=contentlocale:eq:en_CA,en_US&filter_reviews.q0=contentlocale:eq:en_CA,en_US" \
                 "&filter_reviewcomments.q0=contentlocale:eq:en_CA,en_US&resource.q1=reviews" \
                 "&filter.q1=isratingsonly:eq:false&filter.q1=productid:eq:{product_id}" \
                 "&filter.q1=contentlocale:eq:en_CA,en_US&sort.q1=relevancy:a1&stats.q1=reviews&filteredstats.q1=reviews"

    def __init__(self, *args, **kwargs):
        super(MoosejawProductsSpider, self).__init__(*args, **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        # Parse reseller_id
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse buyer reviews
        product_id = response.xpath("//input[@id='adwordsProdId']/@value").extract()

        if product_id:
            response.meta['marks'] = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
            response.meta['product'] = product
            response.meta['product_id'] = product_id[0]
            meta = response.meta

            return Request(
                url=self.REVIEW_URL.format(product_id=product_id[0]),
                dont_filter=True,
                callback=self._parse_buyer_reviews,
                meta=meta
            )

        return product

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('.//*[@itemprop="brand"]/@content').extract()
        return brand[0].strip() if brand else None

    @staticmethod
    def _parse_title(response):
        title = response.xpath('.//*[@id="product_name"]/text()').extract()
        return title[0] if title else None

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = response.xpath('.//span[@id="pd_skuText"]/text()').extract()
        return reseller_id[0] if reseller_id else None

    @staticmethod
    def _parse_price(response):
        fullprice = None
        price = response.xpath('//span[@class="price price-inner "]/span/input[@type="hidden"]/@value').extract()

        if price:
            currency = "USD"
            fullprice = Price(
                price=float(price[0]),
                priceCurrency=currency
            )
        return fullprice

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath("//meta[@property='og:image']/@content").extract()
        image_url = urlparse.urljoin(response.url, image_url[0]) if image_url else None
        return image_url

    @staticmethod
    def _parse_categories(response):
        cats = response.xpath(".//*[@class='breadcrumb-link']//span[@itemprop='title']/text()").extract()
        return cats

    def _scrape_total_matches(self, response):
        total = response.xpath(".//*[@id='searchTotalCount']/text()").extract()
        try:
            if total:
                total = int(re.search('\d+', total[0]).group())
            else:
                total = 0
        except Exception:
            self.log("Exception converting total_matches to int: {}".format(traceback.format_exc()), WARNING)
            total = 0
        finally:
            return total

    def _scrape_product_links(self, response):
        self.product_links = response.xpath(".//*[@class='prod-item__name cf']/@href").extract()

        if not self.product_links:
            self.log("Found no product links.", WARNING)

        for link in self.product_links:
            yield urlparse.urljoin(response.url, link), SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath(
            "//li[@class='paging-controls-itm']"
            "//a[@class='icon-paging-right']/@href").extract()
        if next_page:
            next_page = next_page[0]
            if not self.allowed_domains[0] in next_page:
                next_page = urlparse.urljoin(response.url, next_page)
            return next_page

    def _parse_buyer_reviews(self, response):
        product = response.meta.get('product')

        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        try:
            json_data = json.loads(response.body, encoding='utf-8')
            product_reviews_info = json_data['BatchedResults']['q0']['Results'][0]
            product_reviews_stats = product_reviews_info.get('ReviewStatistics', None)

            if not product_reviews_stats:
                product['buyer_reviews'] = BuyerReviews(**ZERO_REVIEWS_VALUE)
                return product
            if product_reviews_stats:
                rating_by_stars = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
                for rating in product_reviews_stats.get('RatingDistribution', []):
                    rating_value = str(rating.get('RatingValue', ''))
                    if rating_value in rating_by_stars.keys():
                        rating_by_stars[rating_value] = int(rating.get('Count', 0))

                try:
                    average_rating = float(format(product_reviews_stats.get('AverageOverallRating', .0), '.1f'))
                except:
                    average_rating = 0.0

                product['buyer_reviews'] = BuyerReviews(
                    num_of_reviews=int(product_reviews_stats.get('TotalReviewCount', 0)),
                    average_rating=average_rating,
                    rating_by_star=rating_by_stars
                )

        except Exception:
            self.log('Error Parsing Price: {}'.format(traceback.format_exc()), WARNING)

        return product

