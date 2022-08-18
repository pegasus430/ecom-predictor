import json
import re
import traceback
import urlparse

from urlparse import urljoin
from scrapy.conf import settings
from scrapy.log import INFO
from scrapy import FormRequest, Request

from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider, cond_set_value,
                                     FormatterWithDefaults)
from product_ranking.validation import BaseValidator


class FaucetdirectProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'faucetdirect_products'
    allowed_domains = ['faucetdirect.com']

    SEARCH_URL = 'https://www.faucetdirect.com/index.cfm?page=search%3Abrowse&' \
                 'searched=search%3Abrowse&term={search_term}&s={sort_mode}'

    SORT_MODES = {
        'price_asc': 'PRICE_LOW',
        'price_desc': 'PRICE_HIGH',
        'model_number': 'PRODUCT_ID',
        'best_selling': 'SCORE',
        'favorite': 'FAVORITE',
        'rating': 'RATING',
    }

    CAPTCHA_URL = '{referer}/px/captcha/?pxCaptcha={solution}'

    handle_httpstatus_list = [403]

    def __init__(self, sort_mode='best_selling', *args, **kwargs):
        super(FaucetdirectProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                sort_mode=self.SORT_MODES[sort_mode.lower()]
            ), *args, **kwargs)

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        middlewares['product_ranking.middlewares.twocaptcha.TwoCaptchaMiddleware'] = 500

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        settings.overrides[
            'CAPTCHA_SOLVER'] = 'product_ranking.middlewares.captcha.solvers.multicaptcha.MultiCaptchaSolver'

        retry_codes = settings.get('RETRY_HTTP_CODES')
        retry_codes = [c for c in retry_codes if c not in self.handle_httpstatus_list]
        settings.overrides['RETRY_HTTP_CODES'] = retry_codes

    def is_recaptcha(self, response):
        return response.status == 403

    def is_captcha_page(self, response):
        captcha = response.xpath('//form[@id="distilCaptchaForm"]')
        return bool(captcha) or response.status == 403

    def get_captcha_key(self, response):
        pk = response.xpath(
            '//div[@id="funcaptcha"]/@data-pkey |'
            '//div[@class="g-recaptcha"]/@data-sitekey'
        ).extract()
        return pk[0] if pk else None

    def get_captcha_formaction(self, response):
        url = response.xpath('//form[@id="distilCaptchaForm"]/@action').extract()
        return urljoin(response.url, url[0]) if url else None

    def get_funcaptcha_form(self, url, solution, callback):
        return FormRequest(
            url,
            formdata={
                "fc-token": solution
            },
            callback=callback
        )

    def get_captcha_form(self, response, solution, referer, callback):
        uid = re.search(r'window\.px_uuid="(.*?)";', response.body)
        if uid:
            uid = uid.group(1)
        else:
            uid = ""
        vid = re.search(r'window\.px_vid="(.*?)";', response.body)
        if vid:
            vid = vid.group(1)
        else:
            vid = ""
        return Request(
            url=self.CAPTCHA_URL.format(referer=referer, solution=json.dumps({'r': solution, 'v': vid, 'u': uid})),
            callback=callback,
            meta=response.meta
        )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        product['locale'] = "en-US"
        try:
            data = json.loads(
                re.search(
                    'dataLayer\s*=\s*({.+?});',
                    response.body_as_unicode()
                ).group(1)
            )
        except:
            self.log('JSON not found or invalid JSON: {}'.format(traceback.format_exc()))
            product['not_found'] = True
            return product

        item = next((f for f in data.get('finishes', []) if f.get('selectedFinish')), {})

        title = item.get('title')
        cond_set_value(product, 'title', title)

        brand = data.get('manufacturer')
        cond_set_value(product, 'brand', brand)

        sku = item.get('sku')
        cond_set_value(product, 'sku', sku)
        cond_set_value(product, 'reseller_id', sku)

        price = item.get('price', 0)
        cond_set_value(product, 'price', Price('USD', price))

        image_url = item.get('images', {}).get('defaultImg')
        cond_set_value(product, 'image_url', image_url)

        upc = data.get('selectedFinish', {}).get('upc')
        cond_set_value(product, 'upc', upc)

        categories = data.get('breadcrumbs', '').split('|')
        if categories:
            cond_set_value(product, 'categories', categories)
            cond_set_value(product, 'department', categories[-1])

        reviews = self._parse_buyer_reviews(response)
        cond_set_value(product, 'buyer_reviews', reviews)

        variants = self._parse_variants(response, data)
        cond_set_value(product, 'variants', variants)

        in_stock = any([vr.get('in_stock') for vr in variants])
        cond_set_value(product, 'is_out_of_stock', not in_stock)

        return product

    def _parse_variants(self, response, data):
        variants = []
        items = data.get('finishes', [])
        for item in items:
            url = item.get('productLink')
            url = urlparse.urljoin(response.url, url) if url else None
            variant = {
                'properties': {
                    'sku': item.get('sku'),
                    'name': item.get('name'),
                },
                'in_stock': not item.get('isOutOfStock'),
                'price': item.get('price'),
                'url': url,
                'selected': item.get('selectedFinish'),
                'image': item.get('images', {}).get('defaultImg'),
            }
            variants.append(variant)

        return variants

    @staticmethod
    def _parse_buyer_reviews(response):
        num_of_reviews = re.search('"reviewCount":"?(\d+)"?', response.body)
        average_rating = re.search('"ratingValue":"?([\d.]+)"?', response.body)
        if not num_of_reviews or not average_rating:
            return

        buyer_reviews = {
            'num_of_reviews': int(num_of_reviews.group(1)),
            'average_rating': float(average_rating.group(1)),
            'rating_by_star': {},
        }

        return BuyerReviews(**buyer_reviews)

    def _scrape_total_matches(self, response):
        total_matches = re.search('"numberOfItems":(\d+),', response.body_as_unicode())
        if total_matches:
            total_matches = total_matches.group(1)
            return int(total_matches)

    def _scrape_product_links(self, response):
        links = response.xpath('//ul[contains(@id, "category-product")]'
                               '/li[contains(@id, "product")]//div[contains(@class, "product-tile-image")]'
                               '/a/@href').extract()
        if links:
            for link in links:
                yield urlparse.urljoin(response.url, link), SiteProductItem()
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath('//a[@class="nextprev"]/@href').extract()

        if next_page:
            return next_page[0]
