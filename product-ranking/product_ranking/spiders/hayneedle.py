# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import re
import json
import urllib
import urlparse
import traceback

import spiders_shared_code.canonicalize_url

from scrapy.conf import settings
from scrapy import Request, FormRequest

from spiders_shared_code.hayneedle_variants import HayneedleVariants

from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.powerreviews import parse_powerreviews_buyer_reviews


class HayneedleProductSpider(BaseProductsSpider):
    name = 'hayneedle_products'
    allowed_domains = ["www.hayneedle.com", "search.hayneedle.com", "powerreviews.com"]

    SEARCH_URL = "https://search.hayneedle.com/search/?Ntt={search_term}"

    REVIEWS_URL = 'http://readservices-b2c.powerreviews.com/m/9890/l/en_US/product/{sku}/reviews?apikey={api_key}'

    handle_httpstatus_list = [405, 503]

    def __init__(self, *args, **kwargs):
        retry_codes = settings.get('RETRY_HTTP_CODES')
        retry_codes = [c for c in retry_codes if c not in self.handle_httpstatus_list]
        settings.overrides['RETRY_HTTP_CODES'] = retry_codes

        self.TWOCAPTCHA_APIKEY = settings.get('TWOCAPTCHA_APIKEY')
        self.user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 ' \
                          '(KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36'

        super(HayneedleProductSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        middlewares['product_ranking.middlewares.twocaptcha.TwoCaptchaMiddleware'] = 500
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares

        settings.overrides['CAPTCHA_SOLVER'] = 'product_ranking.middlewares.captcha.solvers.recaptcha.RecaptchaSolver'
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        for request in super(HayneedleProductSpider, self).start_requests():
            if self.searchterms:
                request = request.replace(callback=self.parse_redirect)
            yield request

    def parse_redirect(self, response):
        total_matches = self._scrape_total_matches(response)
        if total_matches == 0:
            self.log('There are no available product links')
            prod = SiteProductItem()
            prod['search_term'] = response.meta['search_term']
            prod['url'] = response.url
            if response.status == 200:
                prod['total_matches'] = 0
            if response.status in [301, 302]:
                prod['total_matches'] = 1
                prod['is_redirected'] = True
            return prod
        return self.parse(response)

    @staticmethod
    def get_captcha_key(response):
        captcha_key = response.xpath('//div[@class="g-recaptcha"]/@data-sitekey').extract()
        if captcha_key:
            return captcha_key[0]

    @staticmethod
    def is_captcha_page(response):
        return bool(response.xpath('//div/h1[text()="Pardon Our Interruption..."]'))

    def get_captcha_form(self, response, solution, referer, callback):
        return FormRequest.from_response(
            response,
            formdata={
                "g-recaptcha-response": solution,
                "goto": referer,
                'px': '1'
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded',
                     'Accept': 'text/html,application/xhtml+xml,application/xml;'
                               'q=0.9,image/webp,image/apng,*/*;q=0.8',
                     'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                   'Chrome/65.0.3325.181 Safari/537.36'},
            method='POST',
            callback=callback,
            meta=response.meta
        )

    def canonicalize_url(self, url):
        return spiders_shared_code.canonicalize_url.hayneedle(url)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        # TODO: extract data from json
        meta = response.meta.copy()
        product = meta['product']

        product['no_longer_available'] = self._parse_no_longer_available(response)

        product['url'] = response.url

        # Parse product title
        title = self.parse_title(response)
        cond_set_value(product, 'title', title)

        # Parse brand
        brand = self.parse_brand(response)
        if not brand:
            brand = guess_brand_from_first_words(product.get('title', ''))
        cond_set_value(product, 'brand', brand)

        # Parse sku
        sku = self.parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Parse Image
        image = self.parse_image(response)
        cond_set_value(product, 'image_url', image)

        # Parse locate
        locale = 'en_US'
        cond_set_value(product, 'locale', locale)

        # Parse model
        product_model = self.parse_product_model(response)
        cond_set_value(product, 'model', product_model)

        # Parse reseller id
        reseller_id = self.parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse is_out_of_stock
        product['is_out_of_stock'] = self.parse_is_out_of_stock(response)

        # Parse price
        price = self.parse_price(response)
        product['price'] = price

        hv = HayneedleVariants()
        hv.setupSC(response)
        try:
            product['variants'] = hv._variants()
        except:
            self.log("Error parsing variants {}".format(traceback.format_exc()))

        auth_token = re.search('"pwrApiKey":(.*?)",', response.body)
        if sku and auth_token:
            auth_token = auth_token.group(1).replace('"', '')
            return Request(
                url=self.REVIEWS_URL.format(sku=sku, api_key=auth_token),
                callback=self.parse_buyer_reviews,
                meta={'product': product},
                dont_filter=True
            )

        return product

    @staticmethod
    def parse_count_reviews(response):
        count_review = response.xpath(
            '//div[contains(@class, "pr-snapshot-rating")]//span[contains(@class, "pr-rating")]/text()'
        ).extract()
        return count_review[0] if count_review else None

    @staticmethod
    def parse_image(response):
        images = response.xpath("//div[@class='preloaded-preview-container']/img/@src").extract()
        images_spec = response.xpath("//meta[@property='og:image']/@content").extract()
        image_json = re.search('"imgUrl":(.*?)}', response.body, re.DOTALL)

        if images:
            return images
        elif images_spec:
            return images_spec[0]
        elif image_json:
            return 'http:' + image_json.group(1).replace('\"', '')

    @staticmethod
    def parse_is_out_of_stock(response):
        stock_status = re.search('"availability":(.*?),', response.body)
        if stock_status and 'instock' in stock_status.group(1).lower():
            return False
        return True

    @staticmethod
    def _parse_no_longer_available(response):
        available = response.xpath('//div[contains(@class, "stock-status-button")]/text()').extract()
        if available and available[0].lower() == 'unavailable':
            return True
        return False

    def parse_sku(self, response):
        sku = response.xpath("//row[contains(@class, 'title-container')]//div[contains(@class, 'sku-display')]"
                             "/span[contains(@class, 'text-large')]/following-sibling::span/text()").extract()
        sku_spec = response.xpath("//span[contains(@class, 'standard-style noWrap')]//text()").extract()
        json_sku = re.search('"sku":(.*?),', response.body, re.DOTALL)
        if sku:
            return sku[0]
        elif sku_spec:
            return sku_spec[0]
        elif json_sku:
            return json_sku.group(1).replace('\"', '')

    def parse_price(self, response):
        price_dollar = response.xpath("//*[@class='pdp-dollar-price']/text()").extract()
        price_cent = response.xpath("//*[@class='pdp-cent-price']/text()").extract()
        if price_dollar and price_cent:
            price = '{}.{}'.format(price_dollar[0], price_cent[0])
            price = price.replace(',', '').replace('$', '').strip()
            try:
                return Price(price=float(price), priceCurrency='USD') if not price == '0.00' else None
            except:
                self.log("Error while converting into float".format(traceback.format_exc()))

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    def _scrape_total_matches(self, response):
        search_term_page_data = self._extract_search_term_page_json_data(response)
        if search_term_page_data:
            totals = search_term_page_data.get('totalProductCount')
            if totals:
                return int(totals)
        return 0

    def _scrape_product_links(self, response):
        search_term_page_data = self._extract_search_term_page_json_data(response)

        if search_term_page_data:
            for product_link in search_term_page_data.get('products', []):
                yield product_link['url'], SiteProductItem()
        else:
            self.log('There are no available product links')

    def _scrape_next_results_page_link(self, response):
        search_term_page_data = self._extract_search_term_page_json_data(response)

        try:
            next_page = int(search_term_page_data['pagenation']['nextPage'])

            url_parts = urlparse.urlsplit(response.url)
            page_query = {'page': next_page}
            query = dict(urlparse.parse_qsl(url_parts.query))
            query.update(page_query)
            url_parts = url_parts._replace(query=urllib.urlencode(query))

            return url_parts.geturl()
        except:
            self.log("Found no next link {}".format(traceback.format_exc()))

    def parse_product_id(self, response):
        product_id = self.parse_sku(response)
        return product_id if product_id else None

    @staticmethod
    def parse_title(response):
        title = response.xpath('//div[contains(@class,"pdp-title")]/h1/text()').extract()
        return title[0] if title else None

    @staticmethod
    def parse_brand(response):
        brand = response.xpath('//script/text()').re(r'"brand"\s*:\s*"(.+?)"')
        return brand[0] if brand else None

    @staticmethod
    def parse_product_model(response):
        model = response.xpath(
            '//div[contains(@class, "hero-product-style-color-info")]/@data-stylenumber'
        ).extract()
        return model[0] if model else None

    @staticmethod
    def parse_reseller_id(response):
        reseller_id = re.search(r'/product/(.+?)\.cfm', response.url)
        if reseller_id:
            return reseller_id.group(1).lower()

    def parse_buyer_reviews(self, response):
        product = response.meta.get('product')
        cond_set_value(
            product,
            'buyer_reviews',
            parse_powerreviews_buyer_reviews(response)
        )
        return product

    def _get_products(self, response):
        for req in super(HayneedleProductSpider, self)._get_products(response):
            yield req.replace(dont_filter=True)

    def _extract_search_term_page_json_data(self, response):
        try:
            return json.loads(
                re.search(
                    r'var\s*resultListData\s*=\s*(\{.+?\});',
                    response.body_as_unicode(),
                    re.DOTALL
                ).group(1)
            )
        except:
            self.log('Can not extract json data: {}'.format(traceback.format_exc()))