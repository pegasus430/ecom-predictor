from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback
import urlparse

from lxml import html
from scrapy import Request
from product_ranking.utils import is_empty
from scrapy.log import WARNING
from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words
from scrapy.conf import settings


class DrizlyProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'drizly_products'
    allowed_domains = ["drizly.com"]

    SEARCH_URL = "https://drizly.com/search?utf8=%E2%9C%93&q={search_term}"

    REVIEWS_URL = 'https://w2.yotpo.com/batch'

    agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.98 Safari/537.36"
    headers = {'Content-Type': 'application/json', 'User-agent': agent}

    review_json = None

    def __init__(self, *args, **kwargs):
        super(DrizlyProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args, **kwargs
        )
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        product_json = response.xpath('//script[@type="application/ld+json"]/text()').extract()
        if len(product_json) > 1:
            product_json = json.loads(product_json[1])

        title = self._parse_title(response, product_json)
        cond_set_value(product, 'title', title)

        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        brand = self._parse_brand(response, product_json)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response, product_json)
        cond_set_value(product, 'image_url', image_url)

        self._parse_price(response, product_json)

        product['locale'] = "en-US"

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self._category_name(response)
        product['category'] = category

        pId = response.xpath("//div/@data-catalog-item-id").extract()
        if pId:
            pId = pId[0]
        data_appkey = response.xpath("//div/@data-appkey").extract()
        if data_appkey:
            data_appkey = data_appkey[0]

        if pId and data_appkey:
            data = {"methods": [{"method": "main_widget", "params": {"pid": pId}},
                                {"method": "bottomline",
                                 "params": {"pid": pId,
                                            "link": self.product_url,
                                            "skip_average_score": 'false',
                                            "main_widget_pid": pId
                                            }
                                 }
                                ],
                    "app_key": data_appkey,
                    "is_mobile": "false",
                    "widget_version": "2017-07-03_04-54-40"
                    }

            return Request(
                url=self.REVIEWS_URL,
                method="POST",
                meta={'product': product},
                body=json.dumps(data),
                headers=self.headers,
                callback=self.parse_buyer_reviews,
                dont_filter=True
            )

        return product

    def _parse_title(self, response, product_json):
        title = is_empty(response.xpath('//h1[@class="product-title"]/text()').extract())
        if not title:
            title = product_json.get('name')
        return title

    def _parse_brand(self, response, product_json):
        title = self._parse_title(response, product_json)
        brand = product_json.get('brand')

        if not brand and title:
            brand = guess_brand_from_first_words(title)
        return brand

    def _parse_categories(self, response):
        categories = response.xpath("//span[@property='name']/text()").extract()
        return categories[1:] if categories else None

    def _category_name(self, response):
        category = self._parse_categories(response)
        return category[-1] if category else None

    def _parse_image_url(self, response, product_json):
        image = is_empty(response.xpath("//section[contains(@class, 'product-image')]//img/@src").extract())
        if not image:
            image = product_json.get('image')
        return image

    def _parse_price(self, response, product_json):
        product = response.meta['product']

        price = product_json.get('offers', {}).get('priceSpecification').get('price')

        if price:
            cond_set_value(product, 'price',
                           Price(price=str(price).replace(',', ''),
                                 priceCurrency='USD'))

    def _parse_out_of_stock(self, response):
        oos = response.xpath('.//*[contains(@class, "GreenBold") and contains(text(), "Out of Stock")]')
        return bool(oos)

    def parse_buyer_reviews(self, response):
        average_rating = 0.0
        num_of_reviews = 0

        try:
            content = json.loads(response.body)
            if content:
                self.review_json = content[0]
            if self.review_json.get('result'):
                self.review_json = html.fromstring(self.review_json['result'])

            product = response.meta.get("product")

            rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
            ZERO_REVIEWS_VALUE = {
                'num_of_reviews': 0,
                'average_rating': 0.0,
                'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
            }

            # Get count of Mark
            rating_counts = self.review_json.xpath("//div[@class='yotpo-distibutions-sum-reviews']//span/text()")

            review_list = []
            if len(rating_counts) >= 5:
                review_list = [[5 - i, int(re.findall('\d+', mark)[0])]
                               for i, mark in enumerate(rating_counts)]

            if review_list:
                # average score
                sum = 0
                cnt = 0
                for i, review in review_list:
                    sum += review * i
                    cnt += review
                if cnt > 0:
                    average_rating = round(float(sum) / cnt, 1)

                # number of reviews
                for i, review in review_list:
                    num_of_reviews += review
            else:
                pass

            for i, review in review_list:
                rating_by_star[str(i)] = review

            if average_rating and num_of_reviews:
                buyer_reviews = {
                    'num_of_reviews': int(num_of_reviews),
                    'average_rating': float(average_rating),
                    'rating_by_star': rating_by_star
                }

            else:
                buyer_reviews = ZERO_REVIEWS_VALUE

        except Exception:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()), WARNING)
            buyer_reviews = ZERO_REVIEWS_VALUE

        product['buyer_reviews'] = BuyerReviews(**buyer_reviews)

        return product

    def _scrape_total_matches(self, response):
        total_match = response.xpath("//div[@class='results-meta']/@data-catalog-hits").extract()

        return int(total_match[0]) if total_match else 0

    def _scrape_product_links(self, response):
        self.product_links = response.xpath("//div[@class='CatalogItem']//a/@href").extract()

        for item_url in self.product_links:
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if not self.product_links:
            return
        next_page_link = response.xpath("//div[contains(@class, 'next-page')]//a/@href").extract()
        if next_page_link:
            return urlparse.urljoin(response.url, next_page_link[0])

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()
