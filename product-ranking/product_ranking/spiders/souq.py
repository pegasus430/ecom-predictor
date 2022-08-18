import re

from scrapy.log import INFO, ERROR, WARNING

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import BaseProductsSpider, FLOATING_POINT_RGEX
from product_ranking.utils import is_empty


class SouqProductsSpider(BaseProductsSpider):
    name = 'souq_products'
    allowed_domains = ["souq.com"]
    SEARCH_URL = 'http://uae.souq.com/ae-en/{search_term}/s/?page=1'

    counter = 1

    SORT_MODES = {
        "popularity": "sr",
        "top_rated": "ir_desc",
        "pricelh": "cp_asc",
        "pricehl": "cp_desc",
    }

    def __init__(self, sort_mode=None, *args, **kwargs):
        if sort_mode in self.SORT_MODES:
            self.SEARCH_URL += '&sortby={}'.format(self.SORT_MODES[sort_mode])
        super(SouqProductsSpider, self).__init__(*args, **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = is_empty(response.xpath(
            '//div[contains(@class, "product-title")]/h1/text()').extract())
        product["title"] = title

        product["image_url"] = is_empty(
            response.xpath(
                "//div[contains(@class, 'img-bucket')]/img/@data-url"
            ).extract()
        )

        price = is_empty(response.xpath(
            "//div/h3[contains(@class, 'price')]/text()"
        ).re(FLOATING_POINT_RGEX))
        priceCurrency = is_empty(response.xpath(
            "//div/h3[contains(@class, 'price')]/" \
            "*[contains(@class, 'currency-text')]/text()"
        ).extract(), 'AED')
        if price:
            product["price"] = Price(price=price, priceCurrency=priceCurrency)
            special_pricing = bool(response.xpath('//span[@class="was"]'))
            product["special_pricing"] = special_pricing

        product["description"] = is_empty(response.xpath(
            '//ul/li[@id="description"]').extract())

        stats_xpath = "//dl[contains(@class, 'stats')]/" \
            "dt[contains(text(), '{}')]/following::dd/text()"
        extract_field = lambda field: is_empty(response.xpath(
            stats_xpath.format((field))).extract())

        product["model"] = extract_field('Model Number')
        product['upc'] = extract_field('Item EAN')
        brand = extract_field('Brand')
        if not brand or brand == 'Other':
            brand = guess_brand_from_first_words(title) if title else None
        product['brand'] = brand

        stock_status = re.search('"availability":"(.*?)"', response.body)
        if stock_status:
            product["is_out_of_stock"] = 'OutOfStock' in stock_status.group(1)

        seller_id = re.search('"id_seller":"(\d+)"', response.body)
        if seller_id:
            product['reseller_id'] = seller_id.group(1)

        department = re.search('"category":"(.*?)"', response.body)
        if department:
            product['department'] = department.group(1)

        sku = re.search('"id_item":(\d+)', response.body)
        if sku:
            product['sku'] = sku.group(1)

        buyer_reviews = self._parse_buyer_reviews(response)
        product['buyer_reviews'] = buyer_reviews

        product["locale"] = "en-US"

        return product

    def _parse_buyer_reviews(self, response):
        buyer_reviews = ZERO_REVIEWS_VALUE
        average = is_empty(response.xpath(
            "//div[contains(@class, 'mainRating')]/strong/text()").extract())
        num_of_reviews = is_empty(response.xpath(
            "//div[contains(@class, 'mainRating')]/following::h6/text()"
        ).re(FLOATING_POINT_RGEX))
        if average and num_of_reviews:
            rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
            for item in response.xpath("//div[contains(@class, 'row')]" \
                "/div/div[contains(@class, 'review-rate ')]"):
                star = is_empty(item.xpath(
                    ".//div[1]/span/text()").re(FLOATING_POINT_RGEX))
                value = is_empty(item.xpath(
                    ".//div[last()]/span/text()").re(FLOATING_POINT_RGEX), 0)
                if star:
                    rating_by_star[star] = int(value)
            try:
                num_of_reviews = int(num_of_reviews)
                average = float(average)
            except Exception as e:
                num_of_reviews = 0
                average = 0.0
                self.log('Invalid reviews: {} at {}'.format(
                    str(e), response.url), WARNING)

            buyer_reviews = BuyerReviews(
                average_rating=average,
                num_of_reviews=num_of_reviews,
                rating_by_star=rating_by_star
            )
        return buyer_reviews

    def _scrape_total_matches(self, response):
        total = re.search('"numberOfItems":(\d+)', response.body)
        return int(total.group(1)) if total else 0

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//a[contains(@class, "img-link")]/@href').extract()
        if not links:
            self.log("No products links found.", INFO)
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        url = response.url
        self.counter += 1
        if "page=" in url:
            url = re.sub("(page)=(\d+)", r"\1={}".format(self.counter), url)
        else:
            url += "?page=2"
        total = response.meta.get('total_matches')
        per_page = response.meta.get('products_per_page')
        if total / per_page + 1 > self.counter:
            return url
