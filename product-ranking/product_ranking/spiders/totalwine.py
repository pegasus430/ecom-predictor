from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback
from product_ranking.utils import is_empty
from urlparse import urljoin

from scrapy.conf import settings
from scrapy import Request
from scrapy.log import WARNING
from lxml import html
from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value,\
    FormatterWithDefaults, FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words


class TotalwineProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'totalwine_products'
    allowed_domains = ["www.totalwine.com"]

    SEARCH_URL = "http://www.totalwine.com/search/all?text={search_term}&tab=fullcatalog&page={page_num}"

    REVIEWS_URL = "https://totalwine.ugc.bazaarvoice.com/6595-en_us/{0}/reviews.djs?format=embeddedhtml"

    def __init__(self, *args, **kwargs):
        self.current_page = 1
        settings.overrides['USE_PROXIES'] = True
        formatter = FormatterWithDefaults(page_num=self.current_page)
        super(TotalwineProductsSpider, self).__init__(
            formatter,
            url=self.SEARCH_URL,
            site_name=self.allowed_domains[0],
            *args, **kwargs
        )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        self._parse_price(response)

        product['locale'] = "en-US"

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self._category_name(response)
        cond_set_value(product, 'department', category)

        product_id = response.xpath("//input[@id='productCode']/@value").extract()
        if product_id:
            return Request(
                url=self.REVIEWS_URL.format(product_id[-1]),
                callback=self.parse_buyer_reviews,
                meta={'product': product},
                dont_filter=True
            )

        return product

    def _parse_title(self, response):
        title = response.xpath("//h1[@class='product-name']/text()").extract()
        return self._clean_text(title[-1]) if title else None

    def _parse_categories(self, response):
        categories = response.xpath("//div[@class='breadcrumbs']//li//a/text()").extract()
        return categories[1:] if categories else None

    def _category_name(self, response):
        category = self._parse_categories(response)
        return category[-1] if category else None

    def _parse_image_url(self, response):
        image = response.xpath("//div[contains(@class, 'pdp-tab-overview-prod-img-bottle-img')]//img/@src").extract()
        return urljoin(response.url, image[0]) if image else None

    def _parse_description(self, response):
        description = response.xpath("//div[@class='right-full-desc']//p/text()").extract()
        return description[0] if description else None

    def _parse_currency(self,response):
        price_currency = response.xpath("//meta[@itemprop='priceCurrency']/@content").extract()
        return price_currency[0] if price_currency else 'USD'

    def _parse_price(self, response):
        product = response.meta['product']
        price_currency = self._parse_currency(response)
        price = response.xpath("//meta[@itemprop='price']/@content").re(FLOATING_POINT_RGEX)
        if price:
            cond_set_value(product, 'price',
                           Price(price=price[0].replace(',', ''),
                                 priceCurrency=price_currency))

    def parse_buyer_reviews(self, response):
        rating_counts = []
        review_json = {}
        product = response.meta.get("product")
        contents = response.body_as_unicode()

        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        try:
            start_index = contents.find("webAnalyticsConfig:") + len("webAnalyticsConfig:")
            end_index = contents.find(",\nwidgetInitializers:initializers", start_index)

            review_json = contents[start_index:end_index]
            review_json = json.loads(review_json)

            review_html = html.fromstring(
                re.search('"BVRRSecondaryRatingSummarySourceID":" (.+?)"},\ninitializers={', contents).group(1))

            reviews_by_mark = review_html.xpath("//*[contains(@class, 'BVRRHistAbsLabel')]/text()")
            reviews_by_mark = reviews_by_mark[:5][::-1]

            # Average Rating, Count of Reviews
            if review_json:
                num_of_reviews = review_json["jsonData"]["attributes"]["numReviews"]
                average_rating = round(float(review_json["jsonData"]["attributes"]["avgRating"]), 1)

            if reviews_by_mark:
                rating_counts = [int(re.findall('\d+', mark)[0]) for i, mark in enumerate(reviews_by_mark)]

            if len(rating_counts) == 5:
                rating_by_star = {'1': rating_counts[0], '2': rating_counts[1],
                                  '3': rating_counts[2], '4': rating_counts[3], '5': rating_counts[4]}
            else:
                rating_by_star = {}

            if rating_by_star:
                buyer_reviews_info = {
                    'num_of_reviews': int(num_of_reviews),
                    'average_rating': float(average_rating),
                    'rating_by_star': rating_by_star
                }

            else:
                buyer_reviews_info = ZERO_REVIEWS_VALUE

        except Exception:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()), WARNING)
            buyer_reviews_info = ZERO_REVIEWS_VALUE

        title = product.get('title')
        brand = review_json.get('jsonData', {}).get('brand')
        if not brand and title:
            brand = guess_brand_from_first_words(title)

        product['brand'] = brand
        product['buyer_reviews'] = BuyerReviews(**buyer_reviews_info)

        return product

    def _scrape_total_matches(self, response):
        total_match = response.xpath("//input[@id='listCount']/@value").extract()

        return int(total_match[0]) if total_match else 0

    def _scrape_product_links(self, response):
        product_links = response.xpath("//h2[@class='plp-product-title']//a/@href").extract()

        for item_url in product_links:
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        product_links = response.xpath("//h2[@class='plp-product-title']//a/@href").extract()
        if not product_links:
            return

        self.current_page += 1
        st = response.meta.get('search_term')
        next_link = self.SEARCH_URL.format(search_term=st, page_num=self.current_page)
        return next_link

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()
