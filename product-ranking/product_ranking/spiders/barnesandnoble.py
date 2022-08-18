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
from scrapy.log import ERROR, DEBUG, WARNING


class BarnesandnobleProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'barnesandnoble_products'
    allowed_domains = ["www.barnesandnoble.com"]
    REVIEW_URL = "https://comments.us1.gigya.com/comments.getComments?categoryID=Products&" \
                 "streamID={product_id}&" \
                 "includeStreamInfo=true&" \
                 "lang=en&" \
                 "sort=votesDesc&" \
                 "APIKey=3_MD_HJHUOCjSeK80xcc1NTYJYTlZXtSSDOc3XHyRvw6dcljSs4YVf8OInYiEPtpeE&" \
                 "source=showCommentsUI&" \
                 "authMode=cookie&" \
                 "callback=gigya.callback"
    SEARCH_URL = "http://www.barnesandnoble.com/s/{search_term}?_requestid=948598"

    use_proxies = False

    def __init__(self, *args, **kwargs):
        # All this is to set the site_name since we have several
        # allowed_domains.
        super(BarnesandnobleProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

        self.current_page = 1

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

        desc = self._parse_description(response)
        cond_set_value(product, 'description', desc)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        product["upc"] = self._parse_upc(response)

        product['locale'] = "en-US"

        price = self._parse_price(response)
        product['price'] = price

        is_out_of_stock = self._parse_is_out_of_stock(response)
        product['is_out_of_stock'] = is_out_of_stock

        if product.get('price', None):
            product['price'] = Price(
                price=product['price'].replace(',', '').replace('$', '').strip(),
                priceCurrency="USD"
            )

        product_id = response.xpath('//a[@id="writeReviewBtn"]/@data-work-id').extract()

        if product_id:
            url = self.REVIEW_URL.format(product_id=product_id[0])
            return Request(
                url=url,
                callback=self._parse_buyer_reviews,
                meta={'product': product, 'product_id': product_id[0]},
                dont_filter=True
            )

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//h1[@itemprop="name"]/text()').extract()
        return title[0] if title else None

    @staticmethod
    def _parse_brand(response):
        product = response.meta['product']
        title = product['title']
        brand = None
        if title:
            brand = guess_brand_from_first_words(title)
        return brand

    @staticmethod
    def _parse_image(response):
        image_url = response.xpath('//img[itemprop="image"]/@src').extract()
        return urlparse.urljoin(response.url, image_url[0]) if image_url else None

    def _parse_description(self, response):
        description = response.xpath('//div[@id="productInfoOverview"]'
                                     '//p//text()').extract()

        return self._clean_text("".join(description)) if description else None

    def _parse_price(self, response):
        price = response.xpath('.//*[@itemprop="price"]/text()').extract()

        if not price and self._parse_is_out_of_stock(response):
            price = re.findall(r'"price":{"basePrice":(.*?)},"p', response.body)
            return '$' + price[0] if price else None
        return price[0] if price else None

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath('.//input[@type="hidden" and @name="skuId"]/@value').extract()

        return sku[0] if sku else None

    @staticmethod
    def _parse_upc(response):
        upc = response.xpath('.//dt[contains(text(), "UPC")]/following-sibling::dd[1]/text()').extract()

        return int(upc[0]) if upc else None

    @staticmethod
    def _parse_is_out_of_stock(response):
        is_out_of_stock = re.findall(r'"outOfStock":(.*?),"', response.body)
        if is_out_of_stock:
            return True if is_out_of_stock[0] == 'true' else False

        return False

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']
        product_id = response.meta['product_id']
        is_next = False
        buyer_review_values = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        if response.meta.get('buyer_review_values', None):
            buyer_review_values = response.meta['buyer_review_values']

        try:
            review_json = json.loads(response.body)
            if review_json.get('streamInfo', None):
                stream_info = review_json['streamInfo']
                buyer_review_values['average_rating'] = format(stream_info['avgRatings']['_overall'], '.1f')
                buyer_review_values['num_of_reviews'] = stream_info['ratingCount']

            if review_json.get('comments', None):
                reviews = review_json['comments']
                for review in reviews:
                    rating = str(review['ratings']['_overall'])
                    buyer_review_values['rating_by_star'][rating] += 1
            if review_json.get('next', None):
                next = review_json['next']
                next_start = next.split('|')
                if len(next_start) == 2:
                    if int(next_start[1]) == 0:
                        is_next = True

        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
        finally:
            buyer_reviews = BuyerReviews(**buyer_review_values)
            product['buyer_reviews'] = buyer_reviews
            url = self.REVIEW_URL.format(product_id=product_id) + '&start=' + next
            if is_next:
                return Request(
                    url=url,
                    callback=self._parse_buyer_reviews,
                    meta={'product': product, 'product_id': product_id, 'buyer_review_values': buyer_review_values},
                    dont_filter=True
                )
            else:
                return product

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t]", "", text).strip()

    def _scrape_product_links(self, response):
        product_links = response.xpath('//a[contains(@class, "pImageLink")]/@href').extract()
        if not product_links:
            self.log("Found no product links.", DEBUG)

        for link in product_links:
            yield urlparse.urljoin(response.url, link), SiteProductItem()

    def _scrape_total_matches(self, response):
        totals = response.xpath('//h1[@class="result-show"]/text()').extract()

        if totals:
            totals = re.findall(r'of (.*?) results', totals[0])
            totals = int(totals[0]) if totals else 0
        else:
            totals = 0

        return totals

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath(
            '//a[@class="next-button" and not(@aria-disabled="true")]/@href').extract()
        if next_page:
            return next_page[0]
