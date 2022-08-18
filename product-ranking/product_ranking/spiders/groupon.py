import re
import string
import traceback

from scrapy.conf import settings

from product_ranking.items import (BuyerReviews, Price, SiteProductItem)
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty


class GrouponProductsSpider(BaseProductsSpider):

    name = 'groupon_products'
    allowed_domains = ["groupon.com"]

    SEARCH_URL = "https://www.groupon.com/browse?query={search_term}&locale=en_US"

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'accept-encoding': 'gzip, deflate, sdch, br',
        'accept-language': 'en-US,en;q=0.8',
        'upgrade-insecure-requests': '1',
        'connection': 'keep-alive',
        'user-agent': 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'
    }

    def __init__(self, *args, **kwargs):
        super(GrouponProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        """Generate Requests from the SEARCH_URL and the search terms."""
        for request in super(GrouponProductsSpider, self).start_requests():
            request = request.replace(dont_filter=True, headers=self.headers)
            yield request

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse out of stock
        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Parse buyer reviews
        buyer_reviews = self._parse_buyer_reviews(response)
        cond_set_value(product, 'buyer_reviews', buyer_reviews)

        return product

    def _parse_title(self, response):
        title = response.xpath(
            '//h1[contains(@class, "deal-page-title")]'
            '//text()').extract()
        return title[0].strip() if title else None

    def _parse_categories(self, response):
        categories = response.xpath(
            "//section[@class='breadcrumbs']"
            "//a[@class='crumb']/text()").extract()

        return categories[1:] if categories else None

    @staticmethod
    def _parse_out_of_stock(response):
        oos = False
        oos_info = response.xpath("//div[@class='status-text']/text()").extract()
        if oos_info:
            if 'not yet available' in oos_info[0].lower():
                oos = True

        return oos

    def _parse_price(self, response):
        currency = is_empty(response.xpath(
            "//meta[@itemprop='priceCurrency']/@content").extract(), 'USD')
        price = is_empty(response.xpath(
            "//div[contains(@class, 'breakout-option-price')]/text()").re(r'[-+]?\d*\.\d+|\d+'), 0.00)

        try:
            return Price(price=float(price), priceCurrency=currency)
        except:
            self.log('Price error {}'.format(traceback.format_exc()))

    def _parse_image_url(self, response):
        image_url = is_empty(response.xpath('//meta[@property="og:image"]'
                                            '/@content').extract())
        return image_url

    def _parse_description(self, response):
        desc = response.xpath(
            "//div[@itemprop='description']"
            "/descendant::text()"
        ).extract()

        description = self._clean_text(" ".join(desc))

        bullets_desc = response.xpath(
            "//div[contains(@class, 'fine-print')]"
            "/descendant::text()"
        ).extract()

        if bullets_desc:
            description += self._clean_text(" ".join(bullets_desc))

        description = re.sub(r' +', ' ', description)

        return description

    def _parse_buyer_reviews(self, response):
        average_rating = is_empty(response.xpath(
            "//div[@class='product-reviews-average-rating']/text()").extract(), 0.0)

        num_of_reviews = is_empty(response.xpath(
            "//article[@id='product-reviews']"
            "//a[@class='product-reviews-anchor']/text()").re(r'\d+'), 0)

        if average_rating:
            average_rating = float(average_rating)

        if num_of_reviews:
            num_of_reviews = int(num_of_reviews)

        rating_star_list = response.xpath(
            "//div[@id='product-reviews-quick-view-tooltip']"
            "//table//tr")

        rating_by_star = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        if rating_star_list:
            for rating in rating_star_list:
                try:
                    rating_star_info = rating.xpath(".//ul[@class='product-reviews-rating']/@data-bhc").extract()
                    rating_star = int(re.findall(r'(\d+)', rating_star_info[0])[0])
                    rating_value_info = rating.xpath("./@data-bhc").extract()
                    rating_value = int(re.search('_(\d+)', rating_value_info[0]).group(1))
                    rating_by_star[rating_star] = rating_value
                except Exception as e:
                    print('Error while parsing Reviews: {}'.format(traceback.format_exc(e)))

        return BuyerReviews(num_of_reviews, average_rating, rating_by_star)

    def _parse_sku(self, response):
        sku = is_empty(response.xpath("//meta[@itemprop='sku']/@content").extract())
        return sku

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        """
        Scraping number of resulted product links
        """
        total_matches = is_empty(
            response.xpath('//p[contains(@class, "c-txt-gray-md")]//span/text()').re(r'\d+'), 0
        )

        if total_matches:
            return int(total_matches)
        else:
            return 0

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//figure[contains(@class,"card-ui cui-c-udc")]//a/@href'
        ).extract()
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        links = response.xpath(
            "//ul[@class='pagination-links']"
            "//li[contains(@class, 'selected')]"
            "//following-sibling::li[1]"
            "//a/@href"
        ).extract()
        if links:
            link = links[0]
        else:
            link = None

        return link

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t\r]", "", text).strip()
