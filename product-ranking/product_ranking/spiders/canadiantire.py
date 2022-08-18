# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

import json
import re
import string
import urlparse
import traceback

from scrapy import Request
from scrapy.log import DEBUG, ERROR, WARNING

from product_ranking.items import SiteProductItem, RelatedProduct, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider
from product_ranking.spiders import cond_set, cond_set_value, FormatterWithDefaults
from product_ranking.guess_brand import guess_brand_from_first_words
from scrapy.conf import settings


class CanadiantireProductsSpider(BaseProductsSpider):

    name = 'canadiantire_products'
    allowed_domains = ["www.canadiantire.ca", "canadiantire.ca"]

    SEARCH_URL = "http://api.canadiantire.ca/search/api/v0/product/en/?site=ct;store=0121;q={search_term};format=json;count=36;q=*;"

    CATEGORY_SEARCH_URL = "http://api.canadiantire.ca/search/api/v0/product/en/?site=ct;" \
                          "store=0121;x1=c.cat-level-1;" \
                          "q1={q1};x2=c.cat-level-2;" \
                          "q2={q2};x3=c.cat-level-3;" \
                          "q3={q3};x4=c.cat-level-4;" \
                          "q4={q4};format=json;count=36;q=*;"

    REVIEW_URL = "http://api.bazaarvoice.com/data/reviews.json?Filter=ProductId%3A{product_id}&Include=products&Stats=reviews&apiversion=5.4&passkey=l45q9ns76mpthbmmr0rdmebue&ContentLocale=en_CA"

    PRICE_URL = "http://services.canadiantire.ca/ESB/PriceAvailability?SKU={sku}&Store=0634&Banner=CTR&isKiosk=FALSE&Language=E"
    def __init__(self, *args, **kwargs):
        super(CanadiantireProductsSpider, self).__init__(url_formatter=FormatterWithDefaults(page_num=1),
                                                         site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        self.user_agent = "Mozilla/5.0 (Windows NT 6.1; WOW64) SkypeUriPreview Preview/0.5"
        self.search_term = None
        self.current_page = 1

    def start_requests(self):
        """Generate Requests from the SEARCH_URL and the search terms."""
        for request in super(CanadiantireProductsSpider, self).start_requests():
            if self.product_url:
                request = request.replace(callback=self._parse_single_product)
            else:
                request = request.replace(callback=self._start_requests, dont_filter=True)

            yield request

    def _start_requests(self, response):
        data = json.loads(response.body_as_unicode())
        meta = response.meta
        redirect_url = data.get("redirect")
        if redirect_url:
            yield Request(url='http://www.canadiantire.ca'+redirect_url,
                          dont_filter=True,
                          meta=meta,
                          callback=self._parse_category_url)

        else:
            yield Request(url=self.SEARCH_URL.format(search_term=self.searchterms[0],
                                                     page_num=1),
                          dont_filter=True,
                          meta=meta)

    def _parse_category_url(self, response):
        categories = response.xpath('//li[contains(@class, "global-breadcrumb__item")]/a/text()').extract()
        keyword = response.xpath('//li[contains(@class, "global-breadcrumb__link")]/text()').extract()
        categories = [cat.strip() for cat in categories]
        try:
            url = self.CATEGORY_SEARCH_URL.format(q1=categories[1].replace('&', '%26'), q2=categories[2].replace('&', '%26'),
                                                  q3=categories[3].replace('&', '%26'), q4=keyword[0].strip())
            yield Request(url=url,
                          dont_filter=True,
                          meta={'search_term': self.search_term, 'remaining': self.quantity})
        except:
            self.log("Error while parsing url: {}".format(traceback.format_exc()), WARNING)

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        brand = guess_brand_from_first_words(product['title'])
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        # Product Sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku, conv=string.strip)

        # Parse buyer reviews
        if sku:
            return Request(self.REVIEW_URL.format(product_id=sku+'P'),
                                  dont_filter=True,
                                  meta=response.meta,
                                  callback=self._parse_buyer_reviews)
        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//h2[contains(@class, "product-name")]/text()').extract()
        return title[0].strip() if title else None

    def _parse_price(self, response):
        product = response.meta["product"]
        product["price"] = None
        try:
            data = json.loads(response.body)
            if data[0].get("Price"):
                price = data[0]["Price"]
                currency = 'USD'
                product['price'] = Price(currency, price)
            quantity = data[0].get('Quantity')
            if quantity > 0:
                product['is_out_of_stock'] = False
            else:
                product['is_out_of_stock'] = True
        except:
            self.log("Error while parsing price: {}".format(traceback.format_exc()), WARNING)
        finally:
            return product

    def _parse_image_url(self, response):
        try:
            image_url = response.xpath('//meta[@property="og:image"]/@content').extract()
            return image_url[0].replace('225', '700')
        except:
            self.log("Error while parsing image url: {}".format(traceback.format_exc()), WARNING)

    @staticmethod
    def _parse_description(response):
        description = response.xpath('//li[@class="pdp-details-features__item"]/text()').extract()
        return ''.join(description) if description else None

    @staticmethod
    def _parse_sku(response):
        sku = response.url.split('-')[-1]
        sku = re.search('(\d+)', sku, re.DOTALL)
        if sku:
            return sku.group(1)

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']
        zero_reviews_value = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            data = json.loads(response.body_as_unicode())
            product_id = product['sku'] + 'P'
            results = data.get("Includes", {}).get("Products", {}).get(product_id)

            if not results:
                raise Exception

            data = results.get("ReviewStatistics", {})
            review_count = data.get('TotalReviewCount',0)

            rating_by_star = {}
            stars = data.get("RatingDistribution", [])
            for star in stars:
                rating_by_star[star['RatingValue']] = star['Count']

            average_rating = data.get("AverageOverallRating", 0)

            buyer_reviews = {
                'num_of_reviews': review_count,
                'average_rating': round(float(average_rating), 1) if average_rating else 0,
                'rating_by_star': rating_by_star
            }
            product['buyer_reviews'] = buyer_reviews

        except:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()), WARNING)
            product['buyer_reviews'] = zero_reviews_value

        # Parse price
        sku = product["sku"]
        if sku:
            return Request(url=self.PRICE_URL.format(sku=sku),
                           meta=response.meta,
                           dont_filter=True,
                           callback=self._parse_price)

        cond_set(product, 'title', map(string.strip, response.xpath(
            "//div[@class='productContent']/h1"
            "/div[@id='productName']/text()").extract()))

        cond_set(product, 'brand', response.xpath(
            "//script[contains(text(),'dim7')]"
            "/text()").re(r'.*"dim7":"([^"]*)"}.*'))

        productid = response.xpath(
            "//p[@id='prodNo']/span[@id='metaProductID']/text()")
        if productid:
            productid = productid.extract()[0].strip().replace('P', '')
            try:
                product['upc'] = int(productid)
            except ValueError:
                self.log(
                    "Failed to parse upc number : %r" % productid, WARNING)

        cond_set(product, 'image_url', response.xpath(
            "//div[@class='bigImage']/img[@id='mainProductImage']"
            "/@src").extract())

        price = response.xpath(
            "//div[contains(@class,'bigPrice')]/div[@class='price']"
            "/descendant::*[text()]/text()")
        price = [x.strip() for x in price.extract()]
        price = "".join(price)
        m = re.match(r'\$(.*)\*.*', price)
        if m:
            price = m.group(1)
        cond_set_value(product, 'price',
                       Price('USD', price) if price else None)

        info = response.xpath(
            "//div[@id='features']/div[@class='tabContent']"
            "/descendant::*[text()]/text()")
        if info:
            cond_set_value(product, 'description', " ".join(info.extract()))

        cond_set_value(product, 'locale', "en-US")
        return product

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        total = None
        try:
            data = json.loads(response.body_as_unicode())
            total = data.get("query").get("total-results")
        except:
            self.log("Error parsing json".format(traceback.format_exc()))
        finally:
            return int(total)

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            lists = data.get("results")
            for list in lists:
                item = SiteProductItem()
                link = 'http://www.canadiantire.ca' + list.get("field").get("pdp-url")
                yield link, item
        except:
            self.log("Error parsing json".format(traceback.format_exc()))

    def _scrape_next_results_page_link(self, response):
        if self.current_page < self._scrape_total_matches(response) / response.meta.get('scraped_results_per_page'):
            self.current_page += 1

            next_link = self.SEARCH_URL.format(search_term=response.meta['search_term'],
                                               page_num=self.current_page)
            return next_link
