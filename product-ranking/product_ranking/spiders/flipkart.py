from __future__ import division, absolute_import, unicode_literals

import re
import urlparse
import urllib
import json
import traceback

from scrapy.http import Request
from scrapy.conf import settings
from scrapy.log import WARNING
from product_ranking.items import SiteProductItem, RelatedProduct, Price, \
    BuyerReviews
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults, \
    cond_set, cond_set_value, FLOATING_POINT_RGEX
from product_ranking.utils import is_empty


class FlipkartProductsSpider(BaseProductsSpider):
    name = 'flipkart_products'
    allowed_domains = ["flipkart.com"]

    SEARCH_URL = "https://www.flipkart.com/search?q={search_term}&otracker=start&as-show=off&as=off"

    def __init__(self, *args, **kwargs):
        super(FlipkartProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        """Generate Requests from the SEARCH_URL and the search terms."""
        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8'),)
                ),
                meta={'search_term': st, 'remaining': self.quantity},
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.product_url,
                          callback=self._parse_single_product,
                          meta={'product': prod})

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        model = self._parse_model(response)
        cond_set_value(product, 'model', model)

        self._parse_price(response)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        oos = self._parse_stock(response)
        cond_set_value(product, 'is_out_of_stock', oos)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self._parse_category(response)
        product['department'] = category

        reviews = self._parse_reviews(response)
        product['buyer_reviews'] = reviews

        return product

    def _parse_title(self, response):
        return ''.join(response.xpath("//h1[@class='_3eAQiD']/text()").extract())

    def _parse_image(self, response):
        image_url = response.xpath("//div[@class='_2SIJjY']//img/@src").extract()
        return image_url[0] if image_url else None

    def _parse_description(self, response):
        description = None
        first_description = response.xpath("//div[contains(@class, 'bzeytq')]/text()").extract()

        if first_description:
            description = self._clean_text(first_description[0])
        if not description:
            p_description = response.xpath("//div[contains(@class, 'bzeytq')]//p/text()").extract()
            if p_description:
                description = self._clean_text(p_description[0])

        return description

    def _parse_model(self, response):
        model = re.search('"productId":(.*?)}', response.body)
        return model.group(1).replace('\"', '') if model else None

    def _parse_brand(self, response):
        self._product_json(response)
        brand = None
        try:
            brand = self.product_data['brand']['name']
        except:
            self.log("No brand found".format(traceback.format_exc()), WARNING)
        return brand

    def _parse_price(self, response):
        product = response.meta['product']
        price = response.xpath("//div[@class='_1vC4OE _37U4_g']/text()").extract()
        if len(price) >= 2:
            cond_set_value(product, 'price',
                           Price(price=price[1].replace(',', ''),
                                 priceCurrency='INR'))

    def _parse_categories(self, response):
        categories = response.xpath("//div[@class='_1HEvv0']//a/text()").extract()
        return categories[1:] if categories else None

    def _parse_category(self, response):
        category = self._parse_categories(response)
        return category[-1] if category else None

    def _parse_stock(self, response):
        is_out_of_stock = response.xpath("//div[@class='_3xgqrA']/text()").extract()
        if is_out_of_stock:
            if 'sold out' in is_out_of_stock[0].lower():
                return True
        return False

    def _parse_reviews(self, response):
        zero_reviews_value = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        rating_by_star = {}
        review_count = 0
        average_rating = response.xpath("//div[@class='_1i0wk8']/text()").extract()
        rating_list = response.xpath('//div[@class="CamDho"]/text()').extract()

        try:
            if rating_list:
                for rating in rating_list:
                    review_count = review_count + int(rating.replace(',', ''))

                for i in range(0, 5):
                    rating_by_star[str(5 - i)] = int(rating_list[i].replace(',', ''))

                buyer_reviews = {
                    'num_of_reviews': review_count,
                    'average_rating': round(float(average_rating[0]), 1) if average_rating else 0,
                    'rating_by_star': rating_by_star
                }
            else:
                buyer_reviews = zero_reviews_value

        except Exception:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()), WARNING)
            buyer_reviews = zero_reviews_value

        return BuyerReviews(**buyer_reviews)

    def _product_json(self, response):
        self.product_data = None
        ld_json = is_empty(response.xpath(
            '//*[@type="application/ld+json" '
            'and contains(text(),"product")]/text()').extract())
        if ld_json:
            try:
                clean_json = self._clean_text(ld_json).replace('@', '')
                self.product_data = json.loads(clean_json)[0]
            except:
                self.log("Error while parsing json data: {}".format(traceback.format_exc()), WARNING)

            return self.product_data

    def _scrape_total_matches(self, response):
        total_info = response.xpath("//h1[@class='_1ZODb3']//span/text()").extract()
        total_match = 0

        if total_info:
            total_match = re.search('of(.*?)results', total_info[0])
        if total_match:
            total_match = int(total_match.group(1).replace(',', ''))
        return total_match

    def _scrape_product_links(self, response):
        items = response.xpath("//a[@class='Zhf2z-']/@href").extract()
        for link in items:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page_link = None
        pagination_list = response.xpath("//div[@class='_2kUstJ']//a//span/text()").extract()
        for page_name in pagination_list:
            if 'next' in page_name.lower():
                index = pagination_list.index(page_name)
                next_page_link = response.xpath("//div[@class='_2kUstJ']//a/@href").extract()[index]
                break

        if next_page_link:
            return urlparse.urljoin(response.url, next_page_link)

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()