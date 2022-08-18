# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, unicode_literals

import urlparse
import json
import urllib
import re
import traceback

from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider
from product_ranking.spiders import cond_set_value
from scrapy.log import DEBUG, ERROR
from product_ranking.utils import is_empty
from scrapy.conf import settings
from product_ranking.items import BuyerReviews
from scrapy import Request, FormRequest


class AllModernProductSpider(BaseProductsSpider):
    name = 'allmodern_products'
    allowed_domains = ["www.allmodern.com"]
    start_urls = []
    SEARCH_URL = "https://www.allmodern.com/keyword.php?keyword={search_term}&command=dosearch&new_keyword_search=true"
    zip_code = '12345'

    CAPTCHA_URL = 'https://www.allmodern.com/v/captcha/show?goto={referer}&px=1'

    def __init__(self, *args, **kwargs):
        settings.overrides['USE_PROXIES'] = True
        super(AllModernProductSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

        self.user_agent = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.middlewares.twocaptcha.TwoCaptchaMiddleware'] = 500
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares
        settings.overrides['CAPTCHA_SOLVER'] = 'product_ranking.middlewares.captcha.solvers.recaptcha.RecaptchaSolver'

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        if response.xpath('''.//h1[contains(text(), "Sorry, we couldn't find this page")]'''):
            product["not_found"] = True
            return product

        json_data = self._get_main_product_info(response)

        if json_data:

            # Parse brand
            brand = json_data.get("brand")
            cond_set_value(product, 'brand', brand)

            # Parse title
            title = json_data.get("name")
            cond_set_value(product, 'title', title)

            # Parse out of stock
            is_out_of_stock = self._parse_out_of_stock(json_data)
            cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

            # Parse price
            price = self._parse_price(json_data)
            cond_set_value(product, 'price', price)

            # Parse image url
            image_url = json_data.get("image")
            cond_set_value(product, 'image_url', image_url)

            # Parse buyer reviews
            buyer_reviews = self._parse_buyer_reviews(json_data)
            cond_set_value(product, 'buyer_reviews', buyer_reviews)

            # Parse reseller id
            _reseller_id = json_data.get("sku")
            cond_set_value(product, 'reseller_id', _reseller_id)
            cond_set_value(product, 'sku', _reseller_id)

            # Parse categories
            categories = self._parse_categories(response)
            cond_set_value(product, 'categories', categories)

            if categories:
                cond_set_value(product, 'category', categories[-1])

            # Parse variants
            variants = self._parse_variants(response)
            cond_set_value(product, 'variants', variants)

            return product

    def _get_main_product_info(self, response):
        raw_info = response.xpath('//script[@type="application/ld+json"]/text()').extract()
        try:
            raw_info = json.loads(raw_info[0])
            return raw_info
        except:
            self.log("Failed to load main product info", ERROR)

    @staticmethod
    def _parse_out_of_stock(json_data):
        stock = json_data.get('offers', {}).get('availability')
        if stock and 'instock' in stock.lower():
            return False
        return True

    @staticmethod
    def _parse_price(json_data):
        price = json_data.get("offers", {}).get("price")
        currency = json_data.get("offers", {}).get("priceCurrency")
        if price and currency:
            return Price(
                    price=price,
                    priceCurrency=currency
                )

    @staticmethod
    def _parse_categories(response):
        cats = response.xpath('//ol[@class="Breadcrumbs-list"]/li/a/text()').extract()
        return cats

    def _parse_variants(self, response):
        variants = []

        try:
            json_data = re.search('"bootstrap_data":(.*?),"finalProps"', response.body_as_unicode()).group(1)
            json_data = json.loads('{"bootstrap_data":' + json_data + '}')
            json_data = json_data.get("bootstrap_data", {})
        except:
            self.log("Failed to load main product info", ERROR)
            json_data = {}

        price_data = json_data.get('price', {}).get('optionComboListPriceMapping', {})
        variant_data = json_data.get("options", {}).get('standardOptions', {})
        properties = {}

        for prop in variant_data:
            for prop_option in prop.get('options', {}):
                property_data = {}
                property_data['category_name'] = prop.get('category_name')
                option_id = prop_option.get('option_id')
                property_data['value'] = prop_option.get('name')
                property_data['in_stock'] = prop_option.get('is_active')
                property_data['image_url'] = prop_option.get('thumbnail')
                properties.update({option_id: property_data})

        for price_d in price_data:
            if price_data.get(price_d):
                sku = json_data.get('sku')
                variant = {
                    'reseller_id': sku,
                    'properties': {},
                    'price': price_data.get(price_d)
                }
                if '_' in price_d:
                    price_event = price_d.split('_')
                    variant['in_stock'] = bool(properties.get(str(price_event[0]), {}).get('in_stock'))
                    variant['selected'] = price_event[1] in json_data.get('options', {}).get('selectedOptions', {})
                    variant['url'] = urlparse.urljoin(response.url, '?piid={}'.format(price_event[0] + ',' + price_event[1]))
                    prop_name = properties.get(str(price_event[0]), {}).get('category_name')
                    prop_value = properties.get(str(price_event[0]), {}).get('value')
                    other_prop_name = properties.get(str(price_event[1]), {}).get('category_name')
                    other_prop_value = properties.get(str(price_event[1]), {}).get('value')
                    variant["properties"][prop_name] = prop_value
                    variant["properties"][other_prop_name] = other_prop_value
                    variant["image_url"] = properties.get(str(price_event[0]), {}).get('image_url') or \
                                           properties.get(str(price_event[1]), {}).get('image_url')
                    variants.append(variant)
                else:
                    prop_name = properties.get(str(price_d), {}).get('category_name')
                    variant['selected'] = price_d in json_data.get('options', {}).get('selectedOptions', {})
                    variant['url'] = urlparse.urljoin(response.url, '?piid={}'.format(price_d))
                    variant['in_stock'] = bool(properties.get(str(price_d), {}).get('in_stock'))
                    variant["properties"][prop_name] = properties.get(str(price_d), {}).get('value')
                    variant["image_url"] = properties.get(str(price_d), {}).get('image_url')
                    variants.append(variant)
        if variants:
            return variants

    def _parse_buyer_reviews(self, json_data):
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            rew_num = json_data.get('aggregateRating', {}).get('reviewCount')
            average_rating = json_data.get('aggregateRating', {}).get('ratingValue')
            rating_by_star = {}
            buyer_reviews = {
                'num_of_reviews': rew_num,
                'average_rating': round(float(average_rating), 1),
                'rating_by_star': rating_by_star
            }
            return BuyerReviews(**buyer_reviews)
        except Exception as e:
            self.log("Error while parsing reviews: {}".format(e))
            return BuyerReviews(**ZERO_REVIEWS_VALUE)

    def _scrape_total_matches(self, response):
        total = response.xpath(
            "//section[@class='search-results']/header/h1/span/text()").extract()
        if not total:
            total = response.xpath(
                ".//*[@id='result-count-header-label']/text()").re(r'.*\((\d+)\)')
        if not total:
            total = response.xpath(
                ".//*[@id='filterremovelist']/span/text()").re("(\d+)")
        if not total:
            total = re.findall('"product_count":(\d+)', response.body)
        try:
            total = int(total[0]) if total else 0
        except:
            self.log("Exception converting total_matches to int: {}".format(traceback.format_exc()))
            total = 0
        finally:
            return total

    def _scrape_product_links(self, response):
        links = response.xpath('.//a[contains(@id, "productbox_")]/@href').extract()

        if not links:
            links = response.xpath('//a[@class="ProductCard"]/@href').extract()

        if not links:
            self.log("Found no product links.", DEBUG)

        for link in links:
            yield urlparse.urljoin(response.url, link), SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_link = is_empty(response.xpath('.//a[@data-click-location="PAGINATION:NEXT"]/@href').extract())
        if next_link:
            url = urlparse.urljoin(response.url, next_link)
            return Request(url, meta=response.meta, dont_filter=True)

    @staticmethod
    def get_captcha_key(response):
        captcha_key = response.xpath('//div[@class="g-recaptcha"]/@data-sitekey').extract()
        if captcha_key:
            return captcha_key[0]

    @staticmethod
    def is_captcha_page(response):
        captcha_page = response.url.startswith('https://www.allmodern.com/v/captcha/')
        return bool(captcha_page)

    def get_captcha_form(self, response, solution, referer, callback):
        return FormRequest(
            url=self.CAPTCHA_URL.format(referer=urllib.quote_plus(referer)),
            formdata={
                "g-recaptcha-response": solution,
                "goto": referer,
                'px': '1'
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded',
                     'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                     'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2) '
                                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                                   'Chrome/63.0.3239.132 Safari/537.36'},
            method='POST',
            callback=callback,
            meta=response.meta
        )
