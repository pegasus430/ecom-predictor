# -*- coding: utf-8 -*-
import json
import re
import traceback
import math
import urllib

from urlparse import urljoin
from scrapy import Request
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import (cond_set, cond_set_value, FLOATING_POINT_RGEX,
                                     FormatterWithDefaults, BaseProductsSpider)


class StaplesadvantageProductsSpider(BaseProductsSpider):
    name = "staplesadvantage_products"
    allowed_domains = ['staplesadvantage.com']

    SEARCH_URL = "https://www.staplesadvantage.com/webapp/wcs/stores/servlet" \
                 "/StplCategoryDisplay?term={search_term}" \
                 "&act=4&src=SRCH&reset=true&storeId=10101&pg={page}"

    LOGIN_URL = 'https://www.staplesadvantage.com/webapp/wcs/stores/servlet/StplLogon?' \
                'catalogId=4&langId=-1&storeId=10101'

    payload = {
        "login-domain": "order",
        "userID": "CANDICE@CONTENTANALYTICSINC.COM",
        "password": "Staples1",
        "companyID": "10201633",
        "URL": "redirect",
        "relogonurl": "salogon",
        "errURL": "salogon"
    }

    handle_httpstatus_list = [404]

    def __init__(self, *args, **kwargs):
        super(StaplesadvantageProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(page=1), *args, **kwargs)
        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                          "Chrome/65.0.3325.181 Safari/537.36"
        self.current_page = 1

    def start_requests(self):
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept-Language': 'en-US,en;q=0.8',
            "Origin": "https://www.staplesadvantage.com",
            "Referer": self.LOGIN_URL
        }

        yield Request(
            self.LOGIN_URL,
            method='POST',
            body=urllib.urlencode(self.payload),
            callback=self._start_requests,
            headers=headers
        )

    def _start_requests(self, response):
        return super(StaplesadvantageProductsSpider, self).start_requests()

    def _scrape_total_matches(self, response):
        total = response.css('.didYouMeanNoOfItems').extract()
        if not total:
            total = response.xpath(
                '//span[@class="search-mean-count"]/text()'
            ).extract()
        if not total: return 0
        total = re.search('[\d,]+', total[0])
        return int(total.group().replace(',', '')) if total else 0

    def _scrape_next_results_page_link(self, response):
        total_matches = self._scrape_total_matches(response)
        results_per_page = self._scrape_results_per_page(response)
        if not results_per_page:
            results_per_page = 25
        if (total_matches and results_per_page and
                    self.current_page < math.ceil(total_matches / float(results_per_page))):
            self.current_page += 1
            search_term = response.meta['search_term']
            return self.url_formatter.format(self.SEARCH_URL,
                                             search_term=search_term,
                                             page=self.current_page)

    def _scrape_product_links(self, response):
        links = response.xpath('//div[@class="search-prod-info"]'
                               '//a[contains(@class, "search-prod")]/@href').extract()
        for link in links:
            yield urljoin(response.url, link), SiteProductItem()

    def parse_product(self, response):
        product = response.meta['product']

        if response.status == 404:
            product['not_found'] = True
            return product

        title = response.xpath('//h1[contains(@class, "search-prod-desc")]/text()').extract()
        cond_set(product, 'title', title)
        xpath = '//div[@id="dotcombrand"]/../preceding-sibling::li[1]/text()'
        brand = response.xpath(xpath).extract()
        if not brand:
            brand = response.xpath(
                '//p[@class="brand-name"]/text()'
            ).extract()
            if brand:
                brand = brand[0].split(':')
                if len(brand) == 1:
                    brand = brand[0]
                else:
                    brand = brand[1]
        cond_set_value(product, 'brand', brand.strip() if brand else '')
        xpath = '//h3[text()="Description"]' \
                '/following-sibling::p[normalize-space()] |' \
                '//div[contains(@class, "product-details-desc")]'
        desc = response.xpath(xpath).extract()

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        cond_set(product, 'description', desc)
        image_url = re.findall("enlargedImageURL = '([^']*)'", response.body)
        cond_set(product, 'image_url', image_url)
        model = re.findall('"model" : "([^"]*)"', response.body)
        cond_set(product, 'model', model)
        upc = response.xpath('//input[@name="upcCode"]/@value').extract()
        if upc:
            upc = upc[0][:12].zfill(12)
            cond_set_value(product, 'upc', upc)
        reseller_id = re.findall("currentSKUNbr=(.*?)&", response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, "reseller_id", reseller_id)
        if reseller_id:
            url = "https://yotpo.staplesadvantage.com/v1/widget/" \
                  "RP5gD6RV7AVy75jjXQPUI1AOChyNNClZqkm94Ttb/products/{}" \
                  "/reviews.json?per_page=10&page=1&sort=votes_up" \
                  "&direction=desc&fromAjax=Y".format(reseller_id)

            return Request(url, callback=self._parse_buyer_reviews, meta=response.meta,
                           dont_filter=True)
        else:
            return product

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']
        try:
            data = json.loads(response.body)
            data = data["response"]["bottomline"]
            ratings = data['star_distribution']
            avg = round(float(data['average_score']), 1)
            total = int(data['total_review'])
            cond_set_value(product, 'buyer_reviews',
                           BuyerReviews(total, avg,
                                        ratings) if total else ZERO_REVIEWS_VALUE)
        except:
            self.log("Failed to extract reviews: {}".format(traceback.print_exc()))
            cond_set_value(product, 'buyer_reviews', ZERO_REVIEWS_VALUE)

        return product

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _parse_price(self, response):
        price = response.xpath("//*[@id='autorepricing']//input[@type='hidden']/@value").re(FLOATING_POINT_RGEX)
        if not price:
            price = response.xpath("//div[contains(@class, 'specialoffer-price')]"
                                   "//span[contains(@class, 'specialoffer-price-color')]/text()").re(FLOATING_POINT_RGEX)

        if price:
            return Price(priceCurrency='USD', price=price[0])
