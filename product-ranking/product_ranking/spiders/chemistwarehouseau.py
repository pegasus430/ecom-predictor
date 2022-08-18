from __future__ import division, absolute_import, unicode_literals

import re
import json
import urlparse
import traceback

from scrapy.http import Request

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words
from scrapy.log import DEBUG, WARNING


class ChemistwarehouseauProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'chemistwarehouseau_products'
    allowed_domains = ["www.chemistwarehouse.com.au"]
    REVIEW_URL = "http://api.bazaarvoice.com/data/batch.json?" \
                 "passkey=5tt906fltx756rwlt29pls49v&apiversion=5.5&" \
                 "displaycode=13773-en_au&resource.q0=products&" \
                 "filter.q0=id:eq:{product_id}&" \
                 "stats.q0=reviews&" \
                 "filteredstats.q0=reviews&" \
                 "filter_questions.q0=contentlocale:eq:en_AU&" \
                 "filter_answers.q0=contentlocale:eq:en_AU&" \
                 "filter_reviews.q0=contentlocale:eq:en_AU&" \
                 "filter_reviewcomments.q0=contentlocale:eq:en_AU"
    SEARCH_URL = "http://www.chemistwarehouse.com.au/search?searchtext={search_term}&searchmode=allwords"

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

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        department = self._parse_category(response)
        product['department'] = department

        product['locale'] = "en-US"

        price = self._parse_price(response)
        if price:
            product['price'] = price

        product_id = re.findall(r'"ecomm_prodid": "(.*?)",', response.body)

        if product_id:
            url = self.REVIEW_URL.format(product_id=product_id[0])
            return Request(
                url=url,
                callback=self._parse_buyer_reviews,
                meta={'product': product},
                dont_filter=True
            )

        return product

    @staticmethod
    def _parse_title(response):
        product_name = response.xpath('//div[@itemprop="name"]/h1/text()').extract()
        return product_name[0] if product_name else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        return guess_brand_from_first_words(title) if title else None

    @staticmethod
    def _parse_image(response):
        img_urls = response.xpath('//img[@itemprop="image"]/@src2').extract()
        return img_urls[0] if img_urls else None

    def _parse_categories(self, response):
        categories = response.xpath('//div[@class="breadcrumbs"]/a/text()').extract()
        return categories[1:] if categories else None

    @staticmethod
    def _parse_category(response):
        product = response.meta['product']
        department = product['categories'][-1] if product['categories'] else None
        return department

    def _parse_price(self, response):
        price = response.xpath('//div[@itemprop="price"]//text()').re(r'\d+\.?\d*')
        try:
            return Price(
                price=float(price[0]),
                priceCurrency="AUD"
            )
        except:
            self.log('Error parsing price: {}'.format(traceback.format_exc()), WARNING)
        return None

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']

        buyer_review_values = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            review_json = json.loads(response.body)
            review_statistics = review_json.get("BatchedResults",{}).get("q0",{}).get("Results",[{}])[0].get('ReviewStatistics', {})

            if review_statistics.get("RatingDistribution", None):
                for item in review_statistics['RatingDistribution']:
                    key = str(item['RatingValue'])
                    buyer_review_values["rating_by_star"][key] = item['Count']

            if review_statistics.get("TotalReviewCount", None):
                buyer_review_values["num_of_reviews"] = review_statistics["TotalReviewCount"]

            if review_statistics.get("AverageOverallRating", None):
                buyer_review_values["average_rating"] = format(review_statistics["AverageOverallRating"], '.1f')
        except Exception as e:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
        finally:
            buyer_reviews = BuyerReviews(**buyer_review_values)
            product['buyer_reviews'] = buyer_reviews
            return product

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t]", "", text).strip()

    def _scrape_product_links(self, response):
        product_links = response.xpath('//a[contains(@class, "product-container")]/@href').extract()
        if not product_links:
            self.log("Found no product links.", DEBUG)

        for link in product_links:
            yield urlparse.urljoin(response.url, link), SiteProductItem()

    def _scrape_total_matches(self, response):
        totals = response.xpath('//div[@class="pager-count"]/b/text()').extract()

        if totals:
            totals = re.findall(r'\d+', totals[0])
            totals = int(totals[0]) if totals else 0
        elif not response.xpath('//div[@class="pager-results"]').extract():
            product_links = response.xpath('//a[contains(@class, "product-container")]/@href').extract()
            totals = len(product_links)
        else:
            totals = 0

        return totals

    def _scrape_next_results_page_link(self, response):
        next_page_xpath_str = './/div[@class="pager-results"]/font/following-sibling::a[1]/@href'
        next_page = response.xpath(next_page_xpath_str).extract()
        if next_page:
            return next_page[0]
