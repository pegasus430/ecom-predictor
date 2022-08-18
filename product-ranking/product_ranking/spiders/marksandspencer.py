# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

import re
import json
import math

from scrapy.http import Request

from product_ranking.items import Price, BuyerReviews
from product_ranking.items import SiteProductItem, RelatedProduct
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import BaseProductsSpider, FLOATING_POINT_RGEX
from product_ranking.spiders import cond_set, cond_set_value


is_empty = lambda x, y=None: x[0] if x else y


class MarksandspencerProductsSpider(BaseProductsSpider):
    name = 'marksandspencer_products'
    allowed_domains = ["marksandspencer.com", "recs.richrelevance.com"]

    SEARCH_URL = ("http://www.marksandspencer.com/MSSearchResultsDisplayCmd"
        "?&searchTerm={searchterm}&langId={langId}&storeId={storeId}"
        "&catalogId={catalogId}&categoryId={categoryId}"
        "&typeAhead={typeAhead}&sortBy={sortBy}")

    REVIEW_URL = ("http://reviews.marksandspencer.com/2050-en_gb/"
        "{id}/reviews.djs?format=embeddedhtml")

    SYM_USD = '$'
    SYM_GBP = '£'
    SYM_CRC = '₡'
    SYM_EUR = '€'
    SYM_JPY = '¥'

    CURRENCY_SIGNS = {
        SYM_USD: 'USD',
        SYM_GBP: 'GBP',
        SYM_CRC: 'CRC',
        SYM_EUR: 'EUR',
        SYM_JPY: 'JPY'
    }

    SORT_MODES = {
        "relevance": "relevance|1",
        "best_selling": "product.best_selling|1",
        "new_arrivals": "product.is_new|1",
        "pricelh": "product.price_from|0",
        "pricehl": "product.price_to|1",
        "rating":  "product.rating|1"
    }

    def __init__(self, sort_mode=None, *args, **kwargs):
        self.sort_mode = sort_mode or "relevance"
        super(MarksandspencerProductsSpider, self).__init__(
                site_name=self.allowed_domains[0],
                *args,
                **kwargs)
        self.current_page = 1

    def start_requests(self):
        yield Request(
            url="http://www.marksandspencer.com",
            callback=self.after_start,
        )

    def after_start(self, response):
        storeId = is_empty(response.xpath(
            "//form/.//input[@name='storeId']/@value").extract(), "")
        catalogId = is_empty(response.xpath(
            "//form/.//input[@name='catalogId']/@value").extract(), "")
        categoryId = is_empty(response.xpath(
            "//form/.//input[@name='categoryId']/@value").extract(), "")
        langId = is_empty(response.xpath(
            "//form/.//input[@name='langId']/@value").extract(), "")
        typeAhead = is_empty(response.xpath(
            "//form/.//input[@name='typeAhead']/@value").extract(), "")
        for st in self.searchterms:
            url = self.SEARCH_URL.format(
                searchterm=self.searchterms[0], storeId=storeId,
                catalogId=catalogId, categoryId=categoryId,
                langId=langId, typeAhead=typeAhead,
                sortBy=self.SORT_MODES.get(self.sort_mode)
            )
            yield Request(
                url=url,
                meta={'search_term': st, 'remaining': self.quantity}
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod})

    def parse_product(self, response):
        product = response.meta['product']

        price = response.xpath('//meta[@itemprop="price"]/@content').extract()
        priceCurrency = response.xpath('//meta[@itemprop="priceCurrency"]/@content').extract()
        if price and priceCurrency:
            product["price"] = Price(
                priceCurrency=priceCurrency[0],
                price=price[0],
            )

        image_url = is_empty(response.xpath(
            "//ul[contains(@class, 'custom-wrap')]/li/img/@srcset |"
            "//img[@id='mainProdDefaultImg']/@src"
        ).extract())
        if image_url:
            image_url = image_url.split(',')[0].split(' ')[0]
            if not "http" in image_url:
                image_url = "http:" + image_url
            product["image_url"] = image_url

        cond_set(
            product,
            "brand",
            response.xpath(
                "//ul[contains(@class, 'sub-brand-des')]/li/text()").extract(),
            lambda x: x.strip(),
            )

        cond_set_value(product, "title", is_empty(response.xpath(
            "//h1[@itemprop='name']/text()").extract()))

        cond_set(
            product,
            "model",
            response.xpath("//p[contains(@class, 'code')]/text()").extract(),
            lambda x: x.strip(),
        )

        product["locale"] = "en_GB"

        regex = "\/p\/([a-z0-9$]+)"
        reseller_id = re.findall(regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, "reseller_id", reseller_id)

        variants_stock = is_empty(re.findall(
            "itemStockDetailsMap_\d+\s+\=\s+([^\;]*)", response.body), "{}")
        variants_price = is_empty(re.findall(
            "priceLookMap_\d+\s+\=\s+(.*)};", response.body), "{}")

        try:
            vs = json.loads(variants_stock)
        except (ValueError, TypeError):
            vs = {}
        try:
            vp = json.loads(variants_price+"}")
        except (ValueError, TypeError):
            vp = {}

        variants = []
        for k, v in vs.items():
            for k_in, v_in in vs[k].items():
                obj = {"id": k+"_"+k_in}
                color = is_empty(re.findall("\d+_([^_]*)", k))
                if color:
                    obj["color"] = color
                size = k_in.replace("DUMMY", "")
                if size:
                    obj["size"] = size
                if vs[k][k_in].get("count") == 0:
                    obj["in_stock"] = False
                else:
                    obj["in_stock"] = True
                variants.append(obj)

        for variant in variants:
            price = vp.get(variant["id"], {}).get("price", "")
            price = is_empty(re.findall(FLOATING_POINT_RGEX, price))
            if price:
                variant["price"] = price
            del variant["id"]

        if variants:
            product["variants"] = variants

        reqs = []

        prodId = is_empty(re.findall("productId\s+\=\'(\w+)", response.body))

        if prodId:
            reqs.append(
                Request(
                    url=self.REVIEW_URL.format(id=prodId),
                    callback=self.parse_buyer_reviews,
                )
            )

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def parse_buyer_reviews(self, response):
        product = response.meta.get("product")
        reqs = response.meta.get("reqs")

        total = int(is_empty(response.xpath(
            "//span[contains(@class, 'BVRRRatingSummaryHeaderCounterValue')]"
            "/text()"
        ).re(FLOATING_POINT_RGEX), 0))

        average = float(is_empty(re.findall(
            "avgRating\"\:(\d+\.\d+)", response.body), 0))

        rbs = response.xpath(
            "//span[contains(@class, 'BVRRHistAbsLabel')]/text()"
        ).extract()[:5]
        rbs.reverse()
        rating_by_star = {}
        if rbs:
            for i in range(5, 0, -1):
                rating_by_star[i] = int(rbs[i-1].replace(
                    "\n", "").replace("\t", "").replace("\\n", ""))
        if total and average:
            product["buyer_reviews"] = BuyerReviews(
                num_of_reviews=total,
                average_rating=round(float(average), 1),
                rating_by_star=rating_by_star
            )
        else:
            product["buyer_reviews"] = ZERO_REVIEWS_VALUE

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def send_next_request(self, reqs, response):
        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs
        return req.replace(meta=new_meta)

    def _scrape_total_matches(self, response):
        total_matches = is_empty(response.xpath('//div[@class="total-number-of-items"]'
                                                '/text()').re(FLOATING_POINT_RGEX), 0)
        return int(total_matches.replace(',', ''))

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//h3/a[contains(@class, 'prodAnchor')]/@href").extract()
        if not links:
            links = response.xpath(
                '//li/div[contains(@class, "detail")]/a/@href').extract()
        for link in links:
            yield link+'&pdpredirect', SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page = "&pageChoice={current_page}"
        url = response.url
        total_matches = self._scrape_total_matches(response)
        results_per_page = self._scrape_results_per_page(response)
        if not results_per_page:
            results_per_page = 96
        if (total_matches and results_per_page
            and self.current_page < math.ceil(total_matches / float(results_per_page))):
            self.current_page += 1
            if not "pageChoice=" in url:
                return url + next_page.format(current_page=self.current_page)
        return re.sub("pageChoice=(\d+)", next_page.format(current_page=self.current_page), url)

    def _parse_single_product(self, response):
        return self.parse_product(response)
