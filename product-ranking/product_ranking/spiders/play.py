# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

import json
import re

from product_ranking.items import Price
from product_ranking.items import SiteProductItem, RelatedProduct, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, FLOATING_POINT_RGEX
from product_ranking.spiders import cond_set_value, dump_url_to_file
from scrapy.http import Request
from scrapy.log import DEBUG

is_empty = lambda x, y=None: x[0] if x else y

class PlayProductsSpider(BaseProductsSpider):
    name = 'play_products'
    allowed_domains = ["play.com", "rakuten.co.uk"]
    start_urls = []
    SEARCH_URL = "http://www.rakuten.co.uk" \
        "/search/{search_term}/?l-id=gb_category_search"

    SORT_MODES = {
        'relevance': '1',
        'highest_rating': '5',
        'most_reviews': '6',
        'lowest_price': '2',
        'highest_price': '3',
        'new_arrivals': '4',
    }

    def __init__(self, sort_mode='relevance', *args, **kwargs):
        if sort_mode:
            if sort_mode not in self.SORT_MODES:
                self.log('"%s" not in SORT_MODES')
                sort_mode = 'relevance'
            self.SEARCH_URL += "&s=" + self.SORT_MODES[sort_mode]
        super(PlayProductsSpider, self).__init__(
            None,
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        data = is_empty(re.findall(
            "page_products\'\:\s+([^\}]*)", response.body_as_unicode())) + "}"

        try:
            data = json.loads(data.strip().replace("'", "\""))
        except ValueError:
            data = {}

        product["description"] = is_empty(response.xpath(
                "//div[contains(@class, 'prd-description')]").extract())

        average = is_empty(response.xpath(
            "//span[contains(@class, 'b-rating-average')]/text()").extract())
        total = is_empty(response.xpath(
            "//h2[@class='b-ttl-2']/span/text()").re(FLOATING_POINT_RGEX))
        if average and total:
            product["buyer_reviews"] = BuyerReviews(
                num_of_reviews=total,
                average_rating=average,
                rating_by_star={}
            )

        if data:
            product["price"] = Price(
                price=data["prod_price"],
                priceCurrency=data["currency"]
            )

            product["is_out_of_stock"] = not bool(int(data["stock_available"]))
            product["title"] = data["prod_name"]
            product["image_url"] = data["prod_image_url"]
            product["url"] = data["prod_url"]
            if not product["description"]:
                product["description"] = data["description"]
            product["brand"] = data["brand"]

        else:
            price = is_empty(response.xpath(
                "//span[contains(@class, 'price')]/text()"
            ).re(FLOATING_POINT_RGEX), None)
            if price:
                product["price"] = Price(price=price, priceCurrency="GBP")
            product["title"] = is_empty(response.xpath(
                "//h1[contains(@class, 'b-ttl-main')]/text()").extract())
            product["image_url"] = is_empty(response.xpath(
                "//*[@id='cart-form']/div[2]/div[1]/div/div/a/@href").extract())
            product["url"] = response.url
            product["brand"] = is_empty(response.xpath(
                "//span[@itemprop='brand']/text()").extract())

        if not product.get('brand', None):
            dump_url_to_file(response.url)

        cond_set_value(product, 'locale', "en-GB")

        if "You May Also Like" in response.body_as_unicode():
            catId = is_empty(re.findall(
                "cat_id\'\:\s+(\d+)", response.body_as_unicode()))
            sid = is_empty(re.findall(
                "sid\'\:\s+\"([^\"]*)", response.body_as_unicode()))
            if catId and sid and "item_id" in data:
                url = "http://www.rakuten.co.uk/api/recommendation?" \
                    "category_id=%s" \
                    "&item_id=%s" \
                    "&shop_id=%s" % (catId, data["item_id"], sid)
                return Request(
                    url=url,
                    callback=self._related_parse,
                    meta={"product": product}
                )
        return product

    def _related_parse(self, response):
        product = response.meta['product']
        try:
            data = json.loads(response.body_as_unicode())
        except ValueError:
            return product

        relatedproducts = {"you_may_also_like": []}
        for rel in data:
            relatedproducts["you_may_also_like"].append(
                RelatedProduct(title=rel["name"], url=rel["url"])
            )
        if relatedproducts["you_may_also_like"]:
            product["related_products"] = relatedproducts

        return product

    def _scrape_total_matches(self, response):
        if "Search results for hellowen" in response.body_as_unicode():
            return 0
        total = is_empty(response.xpath(
            "//div[@class='b-tabs-utility']/text()").extract(), 0)
        total = int(is_empty(re.findall("of\s+(\d+)", total), 0))
        return total

    def _scrape_product_links(self, response):
        links = response.xpath("//li[@class='b-item']//b/a/@href").extract()
        if not links:
            self.log("Found no product links.", DEBUG)
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page_links = is_empty(response.xpath(
            "//div[contains(@class, 'b-pagination')]/ul/li[last()]/a/@href"
        ).extract(), None)
        return next_page_links
