from __future__ import division, absolute_import, unicode_literals

import re
import urlparse
import traceback

from scrapy.log import INFO
from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words


class AtgstoresProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'atgstores_products'
    allowed_domains = ["themine.com"]
    SEARCH_URL = "https://www.themine.com/search/{search_term}.html?iterm={search_term}&p={page_number}"

    def __init__(self, *args, **kwargs):
        super(AtgstoresProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(page_number=1),
            *args, **kwargs)

        self.current_page = 1

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        cond_set_value(
            product,
            'title',
            response.xpath("//title/text()").extract()[0].strip())

        brand = guess_brand_from_first_words(product.get('title', '').strip())
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        desc = self._parse_description(response)
        cond_set_value(product, 'description', desc)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        price, currency = self._parse_price(response)
        product['price'] = Price(price=float(price), priceCurrency=currency)

        buyer_reviews = self.parse_buyer_reviews(response)
        product['buyer_reviews'] = buyer_reviews

        product['locale'] = "en-US"

        return product

    def _parse_description(self, response):
        description = response.xpath(
            "//div[@id='prodDesc']//div[@class='mgb8']"
        ).extract()
        if description:
            description = self._clean_text(description[0])

        return description if description else None

    def _parse_categories(self, response):
        categories_list = response.xpath(
            "//div[@id='breadCrumbs']"
            "//a/text()"
        ).extract()
        categories = filter(None, map(self._clean_text, categories_list))

        return categories[1:] if categories else None

    def _parse_price(self, response):
        currency = 'USD'
        price_info = response.xpath("//div[@id='divPrice']/text()").extract()

        if price_info:
            price_info = price_info[0].split('-')
            price = re.sub(r'[,$]', '', price_info[0]).strip()
            return price, currency
        return 0.00, currency

    def _parse_image(self, response):
        image_url = response.xpath("//img[@id='imgProduct']/@src").extract()
        if image_url:
            image_url = urlparse.urljoin('https:', image_url[0])
            return image_url

    def parse_buyer_reviews(self, response):
        rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}

        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        num_of_reviews_info = response.xpath(
            "//a[@class='fnts' and @onclick='showReviews()']/text()").extract()
        num_of_reviews = self._find_number(num_of_reviews_info)

        rating_by_star['5'] = self._find_number(response.xpath("//div[@id='fiveStar']/text()").extract())
        rating_by_star['4'] = self._find_number(response.xpath("//div[@id='fourStar']/text()").extract())
        rating_by_star['3'] = self._find_number(response.xpath("//div[@id='threeStar']/text()").extract())
        rating_by_star['2'] = self._find_number(response.xpath("//div[@id='twoStar']/text()").extract())
        rating_by_star['1'] = self._find_number(response.xpath("//div[@id='oneStar']/text()").extract())

        average_rating = response.xpath("//div[@id='prodRvwStar']/@avgrvw").extract()

        if average_rating:
            average_rating = average_rating[0]
        else:
            average_rating = 0

        buyer_reviews_info = {}
        if rating_by_star:
            buyer_reviews_info = {
                'num_of_reviews': int(num_of_reviews),
                'average_rating': float(average_rating),
                'rating_by_star': rating_by_star
            }

        if buyer_reviews_info:
            return BuyerReviews(**buyer_reviews_info)
        else:
            self.log("Error while parsing reviews")
            return BuyerReviews(**ZERO_REVIEWS_VALUE)

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t]", "", text).strip()

    @staticmethod
    def _find_number(s):
        if not s:
            return 0

        try:
            number = re.findall(r'(\d+)', s[0])[0]
            return int(number)
        except ValueError:
            return 0

    def _scrape_total_matches(self, response):
        total_info = response.xpath(
            "//div[@id='divMsgPage']/text()").extract()
        try:
            total_matches = total_info[0].split('of')
            return int(total_matches[-1])
        except:
            return 0

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//div[@id='divResults']"
            "//div[contains(@class, 'srcheight')]"
            "//div[contains(@class, 'searchImg')]"
            "//a/@href").extract()

        self.product_links = links
        if links:
            for item_url in links:
                yield item_url, SiteProductItem()
        else:
            self.log("Found no product links in {url}".format(
                url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        if not self.product_links:
            return

        self.current_page += 1
        st = response.meta['search_term']

        return self.SEARCH_URL.format(search_term=st, page_number=self.current_page)
