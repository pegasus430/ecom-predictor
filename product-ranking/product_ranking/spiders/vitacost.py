# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

import json
import urllib
import urlparse
import traceback

from scrapy.log import WARNING
from scrapy.http import Request
from scrapy.conf import settings

from product_ranking.validation import BaseValidator
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, \
    FormatterWithDefaults, FLOATING_POINT_RGEX
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi


class VitacostProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'vitacost_products'
    allowed_domains = ["www.vitacost.com"]

    SEARCH_URL = "https://www.vitacost.com/productResults.aspx?N=0&Ntt={search_term}" \
                 "&scrolling=true&No={offset}"

    REVIEW_URL = 'https://api.bazaarvoice.com/data/batch.json?passkey=pgtdnhg3w0npen2to8bo3bbqn&apiversion=5.5' \
                 '&displaycode=4595-en_us&resource.q0=reviews&filter.q0=rating%3Aeq%3A5' \
                 '&filter.q0=isratingsonly%3Aeq%3Afalse&filter.q0=productid%3Aeq%3A{prod_id}&filter.q0' \
                 '=contentlocale%3Aeq%3Aen_US&sort.q0=relevancy%3Aa1&stats.q0=reviews&filteredstats.q0=reviews' \
                 '&include.q0=authors%2Cproducts%2Ccomments&filter_reviews.q0=contentlocale%3Aeq%3Aen_US'

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)

        super(VitacostProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(offset=0),
            site_name=self.allowed_domains[0],
            *args, **kwargs)

        self.user_agent = 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                    offset=0
                ),
                meta={
                    'search_term': st,
                    'remaining': self.quantity,
                    'offset': 0
                }
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod})

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        self._parse_price(response)

        product['locale'] = "en-US"

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        department = self._parse_department(response)
        cond_set_value(product, 'department', department)

        if reseller_id:
            response.meta['reseller_id'] = reseller_id
            return Request(self.REVIEW_URL.format(prod_id=reseller_id),
                           dont_filter=True,
                           meta=response.meta,
                           callback=self.parse_buyer_reviews,
                           )
        return product

    def _parse_reseller_id(self, response):
        reseller_id = response.xpath("//input[@id='bb-productID']/@value").extract()
        return reseller_id[0] if reseller_id else None

    def _parse_title(self, response):
        title = response.xpath("//h1[@itemprop='name']/text()").extract()
        return title[0] if title else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        brand = response.xpath("//a[@itemprop='brand']/text()").extract()

        if brand:
            brand = brand[0]
        if not brand and title:
            brand = guess_brand_from_first_words(title)

        return brand

    def _parse_categories(self, response):
        categories = response.xpath("//h3[contains(@class, 'bcs')]//a/@title").extract()
        return categories if categories else None

    def _parse_department(self, response):
        category = self._parse_categories(response)
        return category[-1] if category else None

    def _parse_image_url(self, response):
        image = response.xpath("//div[@id='productImage']//img/@src").extract()
        return urlparse.urljoin(response.url, image[0]) if image else None

    def _parse_price(self, response):
        product = response.meta['product']
        price = response.xpath("//li[@id='pdpMainPrice']//p[contains(@class, 'pRetailPrice')]").re(FLOATING_POINT_RGEX)
        if price:
            cond_set_value(product, 'price',
                           Price(price=price[0], priceCurrency='USD'))

    def _parse_out_of_stock(self, response):
        oos = response.xpath('.//*[contains(@class, "GreenBold") and contains(text(), "Out of Stock")]')
        return bool(oos)

    def parse_buyer_reviews(self, response):
        buyer_reviews = {}
        product = response.meta['product']
        product_id = response.meta.get('reseller_id')
        try:
            review_json = json.loads(response.body)
            review_statistics = review_json["BatchedResults"]["q0"]["Includes"]['Products'][product_id]['ReviewStatistics']

            if review_statistics.get("RatingDistribution", None):
                by_star = {}
                for item in review_statistics['RatingDistribution']:
                    by_star[str(item['RatingValue'])] = item['Count']
                for sc in range(1, 6):
                    if str(sc) not in by_star:
                        by_star[str(sc)] = 0

                buyer_reviews["rating_by_star"] = by_star

            if review_statistics.get("TotalReviewCount", None):
                buyer_reviews["num_of_reviews"] = review_statistics["TotalReviewCount"]

            if review_statistics.get("AverageOverallRating", None):
                buyer_reviews["average_rating"] = format(review_statistics["AverageOverallRating"], '.1f')
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
        finally:
            if buyer_reviews:
                product['buyer_reviews'] = BuyerReviews(**buyer_reviews)
            else:
                product['buyer_reviews'] = ZERO_REVIEWS_VALUE

        return product

    def _scrape_total_matches(self, response):
        total_matches = response.xpath('//div[@class="srListingNavProducts"]'
                                       '//b/text()').re(FLOATING_POINT_RGEX)
        if total_matches:
            return int(total_matches[0].replace(',', ''))
        return 0

    def _scrape_product_links(self, response):
        links = response.xpath("//div[@class='pb-description']//a/@href").extract()
        for item_url in links:
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()

        st = meta.get('search_term')
        current_page = meta.get('current_page', 1)
        results_per_page = self._scrape_results_per_page(response)
        if not results_per_page:
            results_per_page = 20

        total = self._scrape_total_matches(response)
        offset = current_page * results_per_page

        if total and offset >= total:
            return
        current_page += 1

        meta['current_page'] = current_page
        next_page_link = self.SEARCH_URL.format(offset=offset, search_term=st)

        return Request(
            next_page_link,
            meta=meta
        )