# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals

import json
import re
import traceback
from scrapy import Request, Selector

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import (BuyerReviews, Price, RelatedProduct,
                                   SiteProductItem)
from product_ranking.utils import is_empty
from product_ranking.spiders import (BaseProductsSpider, cond_set,
                                     cond_set_value, FormatterWithDefaults)
from product_ranking.validation import BaseValidator
from product_ranking.validators.levi_validator import LeviValidatorSettings
from spiders_shared_code.levi_variants import LeviVariants


class LeviProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'levieu_products'
    allowed_domains = ["levi.com", "www.levi.com"]
    start_urls = []
    country = "US"
    locale = "en_US"
    i18n_actual = [u"now", u"aktuell", u"à présent"]

    settings = LeviValidatorSettings

    SEARCH_URL = "http://www.levi.com/{country}/{locale}/search?Ntt={search_term}"  # TODO: ordering

    PAGINATE_URL = ('http://www.levi.com/{country}/{locale}/includes/searchResultsScroll/?nao={nao}'
                    '&url=%2FUS%2Fen_US%2Fsearch%3FD%3D{search_term}%26Dx'
                    '%3Dmode%2Bmatchall%26N%3D4294960840%2B4294961101%2B4294965619%26Ntk'
                    '%3DAll%26Ntt%3Ddress%26Ntx%3Dmode%2Bmatchall')

    CURRENT_NAO = 0
    PAGINATE_BY = 120
    TOTAL_MATCHES = None  # for pagination

    REVIEW_URL = "http://levistrauss.ugc.bazaarvoice.com/9090-{locale}/" \
                 "{product_id}/reviews.djs?format=embeddedhtml&page={index}"

    handle_httpstatus_list = [404]

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)

        super(LeviProductsSpider, self).__init__(url_formatter=FormatterWithDefaults(
            country=self.country, locale=self.locale),
            site_name=self.allowed_domains[0], *args, **kwargs)

        self.user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) ' \
                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 ' \
                          'Safari/537.36 (Content Analytics)'

        self.ignore_color_variants = kwargs.get('ignore_color_variants', True)
        if self.ignore_color_variants in ('0', False, 'false', 'False'):
            self.ignore_color_variants = False
        else:
            self.ignore_color_variants = True

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta.get('product', SiteProductItem())

        if response.status == 404 \
                or 'This product is no longer available' in response.body_as_unicode() \
                or "www.levi.com/{}/{}/error".format(self.country, self.locale) in response.url:
            product.update({"not_found": True})
            product.update({"no_longer_available": True})
            return product

        reqs = []

        # product id
        self.product_id = is_empty(response.xpath('//meta[@itemprop="model"]/@content').extract())

        # product data in json
        self.js_data = self.parse_data(response)

        # Parse locate
        cond_set_value(product, 'locale', self.locale)

        # Parse model
        cond_set_value(product, 'model', self.product_id)

        # Parse title
        title = self.parse_title(response)
        cond_set_value(product, 'title', title)

        # Parse image
        image = self.parse_image()
        cond_set_value(product, 'image_url', image)

        # Parse brand
        brand = self.parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # Parse upc
        upc = self.parse_upc()
        cond_set_value(product, 'upc', upc)

        # Parse sku
        sku = self.parse_sku()
        cond_set_value(product, 'sku', sku)

        # Parse price
        price = self.parse_price(response)
        cond_set_value(product, 'price', price)

        reseller_id_regex = "p\/(\d+)"
        reseller_id = re.findall(reseller_id_regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, 'reseller_id', reseller_id)

        try:
            variants = self._parse_variants(response)
            product['variants'] = variants
        except KeyError:
            product['not_found'] = True
            return product

        response.meta['marks'] = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        real_count = is_empty(re.findall(r'<span itemprop="reviewCount">(\d+)<\/span>',
                                         response.body_as_unicode()))
        if real_count:
            # Parse buyer reviews
            if int(real_count) > 8:
                for index, i in enumerate(xrange(9, int(real_count) + 1, 30)):
                    reqs.append(
                        Request(
                            self.url_formatter.format(self.REVIEW_URL,
                                                      product_id=self.product_id, index=index + 2),
                            dont_filter=True,
                            callback=self.parse_buyer_reviews
                        )
                    )

        reqs.append(
            Request(
                self.url_formatter.format(self.REVIEW_URL,
                                          product_id=self.product_id, index=0),
                dont_filter=True,
                callback=self.parse_buyer_reviews
            ))

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_variants(self, response):
        """
        Parses product variants.
        """
        lv = LeviVariants()
        lv.setupSC(response, self.ignore_color_variants)
        variants = lv._variants()

        return variants

    def parse_buyer_reviews(self, response):
        meta = response.meta.copy()
        buyer_reviews_per_page = self.br.parse_buyer_reviews_per_page(response)

        for k, v in buyer_reviews_per_page['rating_by_star'].iteritems():
            response.meta['marks'][k] += v

        product = response.meta['product']
        reqs = meta.get('reqs')

        product['buyer_reviews'] = BuyerReviews(
            num_of_reviews=buyer_reviews_per_page['num_of_reviews'],
            average_rating=buyer_reviews_per_page['average_rating'],
            rating_by_star=response.meta['marks']
        )

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """

        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs

        return req.replace(meta=new_meta)

    def parse_brand(self, response):
        brand = is_empty(response.xpath(
            '//meta[@itemprop="brand"]/@content').extract())

        return brand

    def parse_title(self, response):
        title = response.xpath(
            '//meta[contains(@property, "og:title")]/@content').extract()
        if title:
            title = [title[0].replace('&trade;', '').replace('\u2122', '')]
        else:
            title = response.xpath(
                '//h1[contains(@class, "title")]/text()').extract()
        return is_empty(title)

    def parse_data(self, response):
        try:
            data = re.findall(r'var\s?buyStackJSON\s?=\s?[\'\"](.+?)[\'\"];', response.body_as_unicode())
            data = re.sub(r'\\(.)', r'\g<1>', data[0])
            return json.loads(data)
        except:
            self.log("Failed to parse json response: %s", traceback.format_exc())
            return {}

    def parse_image(self):
        return self.js_data.get('colorid', {}).get(self.product_id, {}).get('gridUrl')

    def parse_upc(self):
        for v in self.js_data.get('sku', {}).values():
            upc = v.get('ean', '')
        return upc[-12:]

    def parse_sku(self):
        for v in self.js_data.get('sku', {}).values():
            skuid = v.get('skuid')

        return skuid

    def parse_price(self, response):
        if self.js_data:
            price = self.js_data['colorid'][self.product_id]['price']
            for price_data in price:
                if price_data['il8n'] in self.i18n_actual:
                    try:
                        price = float(re.findall('\d*\,\d+|\d+', price_data['amount'])[0].replace(',', '.'))
                    except Exception as e:
                        self.log('Price Error {}', traceback.format_exc(e))
            currency = is_empty(re.findall(r'currency":"(\w+)"', response.body_as_unicode()))

            if price and currency:
                price = Price(price=price, priceCurrency=currency)
            else:
                price = Price(price=0.00, priceCurrency="USD")

            return price

    def _scrape_total_matches(self, response):
        totals = response.css('.productCount ::text').extract()
        if totals:
            totals = totals[0].replace(',', '').replace('.', '').strip()
            if totals.isdigit():
                if not self.TOTAL_MATCHES:
                    self.TOTAL_MATCHES = int(totals)
                return int(totals)

    def _scrape_product_links(self, response):
        for link in response.xpath(
                '//li[contains(@class, "product-tile")]'
                '//a[contains(@rel, "product")]/@href'
        ).extract():
            yield link, SiteProductItem()

    def _get_nao(self, url):
        nao = re.search(r'nao=(\d+)', url)
        if not nao:
            return
        return int(nao.group(1))

    def _replace_nao(self, url, new_nao):
        current_nao = self._get_nao(url)
        if current_nao:
            return re.sub(r'nao=\d+', 'nao=' + str(new_nao), url)
        else:
            return url + '&nao=' + str(new_nao)

    def _scrape_next_results_page_link(self, response):
        if self.TOTAL_MATCHES is None:
            self.log('No "next result page" link!')
            return
        if self.CURRENT_NAO + self.PAGINATE_BY < self.TOTAL_MATCHES:
            self.CURRENT_NAO += self.PAGINATE_BY
            return Request(
                self.url_formatter.format(self.PAGINATE_URL,
                                          search_term=response.meta['search_term'],
                                          nao=str(self.CURRENT_NAO)),
                callback=self.parse, meta=response.meta
            )
