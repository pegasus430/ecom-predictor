# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals
import re
from scrapy import Request, FormRequest
import urlparse
from product_ranking.utils import is_empty
from product_ranking.amazon_tests import AmazonTests
from product_ranking.amazon_base_class import AmazonBaseClass
from product_ranking.validators.amazonca_validator import AmazoncaValidatorSettings
from product_ranking.items import SiteProductItem
from product_ranking.spiders import cond_set_value
import json
from scrapy.log import INFO, WARNING, ERROR

class AmazonBestSellersProductsSpider(AmazonTests, AmazonBaseClass):
    name = 'amazon_top_categories_products'
    allowed_domains = ["amazon.com", "asintoupc.com", "walmart.com", "target.com", 'http://psp-gps.info']

    settings = AmazoncaValidatorSettings
    ASIN_UPC_URL = "http://asintoupc.com"

    ASIN_UPC_URL_A = "http://psp-gps.info/index.php?i={}"

    handle_httpstatus_list = [429]

    def __init__(self, *args, **kwargs):
        super(AmazonBestSellersProductsSpider, self).__init__(*args, **kwargs)
        # Optional flags to match target and walmart respectively, turned off by default
        self.match_walmart = kwargs.get('match_walmart', None)
        if self.match_walmart in ('1', True, 'true', 'True'):
            self.match_walmart = True
        else:
            self.match_walmart = False

        self.match_target = kwargs.get('match_target', None)
        if self.match_target in ('1', True, 'true', 'True'):
            self.match_target = True
        else:
            self.match_target = False

        # String from html body that means there's no results ( "no results.", for example)
        self.total_match_not_found_re = 'did not match any products.'
        # Regexp for total matches to parse a number from html body
        self.total_matches_re = r'of\s?([\d,.\s?]+)'
        self.over_matches_re = r'over\s?([\d,.\s?]+)'

        # Default price currency
        self.price_currency = 'USD'
        self.price_currency_view = '$'

        # Locale
        self.locale = 'en-US'
        # settings.overrides['USE_PROXIES'] = True

    def start_requests(self):
        if self.product_url:
            yield Request(self.product_url)
        if self.products_url:
            urls = self.products_url.split('||||')
            for url in urls:
                yield Request(url)

    def parse(self, response):
        url = response.url + '?pg={}&ajax=1&isAboveTheFold={}'
        shelf_name = response.xpath('//h1/span[@class="category"]/text()').extract()
        shelf_name = [s.strip() for s in shelf_name if s.strip()]
        shelf_path = response.xpath(
                    '//li[@class="zg_browseUp"]/a/text()').extract()[1:] + response.xpath(
                    '//span[@class="zg_selected"]/text()').extract()
        shelf_path = [s.strip() for s in shelf_path if s.strip()]
        for page in range(1, 6):
            for position in [1, 0]:
                request = Request(url=url.format(page, position),
                                  callback=self._scrape_product_links,
                                  dont_filter=True)
                request.meta['shelf_name'] = shelf_name
                request.meta['shelf_path'] = shelf_path
                yield request

    def _scrape_product_links(self, response):
        products = response.xpath('//div[@class="zg_itemImmersion"]')
        for product in products:
            url = is_empty(product.xpath(
                './/div[@class="zg_itemWrapper"]/div/a/@href').extract())
            if not url:
                self.log('url not found', WARNING)
                continue
            url = urlparse.urljoin(response.url, url)
            request = Request(url=url, callback=self.parse_product)
            request.meta['shelf_name'] = response.meta.get('shelf_name')
            request.meta['shelf_path'] = response.meta.get('shelf_path')
            request.meta['ranking'] = is_empty(product.xpath(
                './/span[@class="zg_rankNumber"]/text()').re('\d+'))
            request.meta['product'] = SiteProductItem()
            yield request

    def parse_product(self, response):
        product = response.meta.get('product') if response.meta.get('product') else SiteProductItem()
        cond_set_value(product, 'shelf_path', response.meta.get('shelf_path'))
        cond_set_value(product, 'shelf_name', response.meta.get('shelf_name'))
        title = response.xpath('//h1/span/text()').extract()[0].strip()
        cond_set_value(product, 'title', title)
        data_body = response.xpath('//script[contains(text(), '
                                   '"merchantID")]/text()').extract()
        try:
            asin = re.findall(r'"ASIN" : "(\w+)"', data_body[0])[0]
        except IndexError:
            asin = re.findall('\/([A-Z0-9]{10})', response.url)[0]
        cond_set_value(product, 'asin', asin)
        cond_set_value(product, 'url', response.url)
        cond_set_value(product, 'ranking', response.meta.get('ranking'))
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        if self.match_target or self.match_walmart:
            req = Request(url='http://asintoupc.com', callback=self.get_payload, dont_filter=True)
            req.meta['product'] = product
            yield req
        else:
            yield product

        # req = Request(url=self.ASIN_UPC_URL.format(asin), callback=self.threadsafe_ASIN2UPC, dont_filter=True)
        # req = Request(url=self.ASIN_UPC_URL_A.format(product.get('asin')), callback=self.ASIN2UPC_alternative,
        #               dont_filter=True)

    def ASIN2UPC_alternative(self, response):
        product = response.meta.get('product')
        if response.xpath('.//*[contains(text(), "Please change this value and retry your request")]'):
            yield product
        else:
            upc = response.xpath('.//b[contains(text(), "UPC:")]/following-sibling::text()[1]').extract()
            upc = upc[0].strip() if upc else None

            if upc:
                self.log("Got UPC: {}".format(upc), level=INFO)
                cond_set_value(product, 'upc', upc)
                if self.match_walmart:
                    req = Request('http://www.walmart.com/search/?query={}'.format(upc),
                                  callback=self._match_walmart_threadsafe)
                    req.meta['product'] = product
                    yield req
                elif self.match_target:
                    target_url = 'http://tws.target.com/searchservice/item/search_results/v2/by_keyword?search_term={}&alt=json&' \
                                 'pageCount=24&response_group=Items&zone=mobile&offset=0'
                    req = Request(target_url.format(upc), callback=self._match_target_threadsafe)
                    req.meta['product'] = product
                    yield req
            else:
                self.log("No UPC for ASIN {} at {}".format(product.get('asin'), response.url), level=INFO)
                yield product

    def get_payload(self, response):
        product = response.meta.get('product')
        if response.status == 429 or response.status == 500:
            req = Request(url=self.ASIN_UPC_URL_A.format(product.get('asin')),
                          callback=self.ASIN2UPC_alternative, dont_filter=True)
            req.meta['product'] = product
            self.log("Page error, trying other service", level=WARNING)
            yield req
        else:
            payload = {
                r"ctl00$MainContent$txtASIN": product.get('asin'),
                r"ctl00$MainContent$btnSearch": "Search",
            }
            for input_name in ['__VIEWSTATE', '__VIEWSTATEGENERATOR', '__EVENTVALIDATION']:
                pl = response.xpath("//input[@name='%s']/@value" % input_name).extract()
                payload[input_name] = pl[0] if pl else ''

            req = FormRequest(url=self.ASIN_UPC_URL.format(product.get('asin')), callback=self.threadsafe_ASIN2UPC,
                          dont_filter=True, formdata=payload)

            req.meta['product'] = product
            yield req

    def threadsafe_ASIN2UPC(self, response):
        product = response.meta.get('product')
        if response.status == 429 or response.status == 500:
            req = Request(url=self.ASIN_UPC_URL_A.format(product.get('asin')),
                          callback=self.ASIN2UPC_alternative, dont_filter=True)
            req.meta['product'] = product
            self.log("Page error, trying other service", level=WARNING)
            yield req
        else:
            if 'WSE101: An asynchronous operation raised an exception.' in response.body_as_unicode():
                req = Request(url=self.ASIN_UPC_URL_A.format(product.get('asin')),
                              callback=self.ASIN2UPC_alternative, dont_filter=True)
                req.meta['product'] = product
                self.log("Page error, trying other service", level=WARNING)
                yield req
            else:
                upc = response.xpath("//span[@id='MainContent_lblUPC']/text()").extract()
                upc = upc[0] if upc else None
                if upc:
                    self.log("Got UPC: {}".format(upc), level=INFO)
                    cond_set_value(product, 'upc', upc)
                    if self.match_walmart:
                        req = Request('http://www.walmart.com/search/?query={}'.format(upc),
                                      callback=self._match_walmart_threadsafe)
                        req.meta['product'] = product
                        yield req
                    elif self.match_target:
                        target_url = 'http://tws.target.com/searchservice/item/search_results/v2/by_keyword?search_term={}&alt=json&' \
                                     'pageCount=24&response_group=Items&zone=mobile&offset=0'
                        req = Request(target_url.format(upc), callback=self._match_target_threadsafe)
                        req.meta['product'] = product
                        yield req
                else:
                    self.log("No UPC for ASIN {} at {}".format(product.get('asin'), response.url), level=INFO)
                    yield product

    def _match_walmart_threadsafe(self, response):
        product = response.meta.get('product')
        upc = product.get('upc')
        walmart_category = response.xpath('//p[@class="dept-head-list-heading"]/a/text()').extract()
        walmart_url = response.xpath('//a[@class="js-product-title"][1]/@href').extract()
        if walmart_url:
            walmart_exists = True
            walmart_url = urlparse.urljoin('http://www.walmart.com/', walmart_url[0])
        else:
            walmart_exists = False
        cond_set_value(product, 'walmart_url', walmart_url)
        cond_set_value(product, 'walmart_category', walmart_category)
        cond_set_value(product, 'walmart_exists', walmart_exists)
        # This is for case when both flags are true
        if self.match_target:
            target_url = 'http://tws.target.com/searchservice/item/search_results/v2/by_keyword?search_term={}&alt=json&' \
                         'pageCount=24&response_group=Items&zone=mobile&offset=0'
            req = Request(target_url.format(upc), callback=self._match_target_threadsafe)
            req.meta['product'] = product
            yield req
        else:
            yield product

    def _match_target_threadsafe(self, response):
        product = response.meta.get('product')
        json_response = json.loads(response.body_as_unicode())
        try:
            item = json_response['searchResponse']['items']['Item']
            item = item[0] if item else None
            if item:
                target_category = item['itemAttributes']['merchClass']
                target_url = item['productDetailPageURL']
                if target_url:
                    target_exists = True
                    target_url = urlparse.urljoin('http://www.target.com/', target_url)
                else:
                    target_exists = False
                cond_set_value(product, 'target_url', target_url)
                cond_set_value(product, 'target_category', [target_category])
                cond_set_value(product, 'target_exists', target_exists)
            else:
                target_exists = False
                cond_set_value(product, 'target_url', [])
                cond_set_value(product, 'target_category', [])
                cond_set_value(product, 'target_exists', target_exists)
        except Exception:
            pass
        yield product
