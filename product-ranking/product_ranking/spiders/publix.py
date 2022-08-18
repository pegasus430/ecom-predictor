from __future__ import division, absolute_import, unicode_literals

import re
import urlparse
import itertools
import traceback
import json

from scrapy.http import Request

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults, FLOATING_POINT_RGEX
from scrapy.log import DEBUG, WARNING
from product_ranking.guess_brand import guess_brand_from_first_words


class PublixProductsSpider(BaseProductsSpider):
    name = 'publix_products'
    allowed_domains = ["www.publix.com"]

    COOKIE = '{store_number}|{store_string}'
    STORE_STRING = 'http://services.publix.com/api/v1/storelocation/{store_number}'
    SEARCH_URL = 'http://www.publix.com/product-catalog/productlisting?query={search_term}&page={page_num}&count=96'

    def __init__(self, store='1083', *args, **kwargs):
        self.store = store
        self.store_strong = None
        self.total_matches = None
        self.cookies = None
        self.zip = None
        url_formatter = FormatterWithDefaults(page_num=1)
        super(PublixProductsSpider, self).__init__(url_formatter=url_formatter,
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def start_requests(self):
        url = self.STORE_STRING.format(store_number=self.store)
        yield Request(
            url,
            self.get_store_string,
            headers={
                'Accept': 'application/json, text/javascript, */*; q=0.01'
            }
        )

    def get_store_string(self, response):
        try:
            data = json.loads(response.body)
            store = data.get('Stores', [])[0]
            self.store = store.get('KEY')
            store_string = store.get('NAME')
            self.zip = store.get('ZIP')
        except:
            self.log('Can not parse the store string json: {}'.format(traceback.format_exc()), WARNING)
            store = re.search(r'<KEY>(.*?)</KEY>', response.body)
            if store:
                self.store = store.group(1)
            store_string = re.search(r'<NAME>(.*?)</NAME>', response.body)
            store_string = store_string.group(1) if store_string else None
        if self.store and store_string:
            self.cookies = {
                'PublixStore': self.COOKIE.format(store_number=self.store, store_string=store_string)
            }
            for request in super(PublixProductsSpider, self).start_requests():
                yield request.replace(cookies=self.cookies)
        else:
            self.log('Can not parse the key and name')

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        if title:
            brand = guess_brand_from_first_words(title)
            cond_set_value(product, 'brand', brand)

        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        department = self._parse_department(response)
        product['department'] = department

        product['locale'] = "en-US"

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        save_amount = self._parse_save_amount(response)
        cond_set_value(product, 'save_amount', save_amount)

        cond_set_value(product, 'promotions', bool(save_amount))

        cond_set_value(product, 'variants', self._parse_variants(response))

        cond_set_value(product, 'store', self.store)

        cond_set_value(product, 'zip_code', self.zip)

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//span[contains(@id, "ProductSummary_productTitleLabel")]/text()').extract()
        return title[0] if title else None

    @staticmethod
    def _parse_image(response):
        image_url = response.xpath('//div[@id="ProductImages"]'
                                   '//div[@class="thumbnails"]'
                                   '//img[contains(@class, "productImage-s")]'
                                   '/@data-largimage').extract()
        return urlparse.urljoin(response.url, image_url[0]) if image_url else None

    def _parse_categories(self, response):
        categories = response.xpath('//ul[@class="breadcrumb"]//li//a/text()').extract()
        category_list = filter(None, map(self._clean_text, categories))
        return category_list[1:-1] if category_list else None

    def _parse_department(self, response):
        categories = self._parse_categories(response)
        return categories[-1] if categories else None

    @staticmethod
    def _parse_price(response):
        price = response.xpath('//input[@id="finalPrice"]/@value').extract()
        return Price(price=float(price[0]), priceCurrency='USD') if price else None

    @staticmethod
    def _parse_save_amount(response):
        save_amount = response.xpath(
            '//span[@id="content_1_3fourthswidth2colright_0_ProductSummary_SavingMsg"]/text()'
        ).re(FLOATING_POINT_RGEX)
        return save_amount[0] if save_amount else None

    @staticmethod
    def _parse_variants(response):
        attributes = response.xpath(
            '//div[contains(@class, "options")]//div[contains(@class, "dropdown-option")]//select[@data-alert-bot]'
        )
        attr_list = []
        values_list = []
        for attr in attributes:
            key = attr.xpath('./@data-alert-bot').extract()
            values = attr.xpath('.//option[position() > 1]/text()').extract()
            if not all([key, values]):
                continue
            attr_list.append(key[0])
            values_list.append(values)
        if not all([attr_list, values_list]):
            return
        combine_list = itertools.product(*values_list)
        variant_list = []
        for com in combine_list:
            variant = {
                'properties': {}
            }
            for index, attribute in enumerate(attr_list):
                variant['properties'][attribute] = com[index]
            variant_list.append(variant)
        return variant_list

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t]", "", text).strip()

    def _get_products(self, response):
        for request in super(PublixProductsSpider, self)._get_products(response):
            if isinstance(request, Request):
                request = request.replace(cookies=self.cookies, dont_filter=True)
            yield request

    def _scrape_product_links(self, response):
        product_links = response.xpath('//div[@class="main-image"]/a/@href').extract()

        if not product_links:
            self.log("Found no product links.", DEBUG)

        for link in product_links:
            yield link, SiteProductItem()

    def _scrape_total_matches(self, response):
        if self.total_matches:
            return self.total_matches
        totals = response.xpath('//span[@id="total"]/text()').extract()
        self.total_matches = int(totals[0]) if totals else None
        return self.total_matches

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        current_page = meta.get('current_page')
        if not current_page:
            current_page = 1
        if current_page * 96 >= self.total_matches:
            return
        current_page += 1
        st = meta.get('search_term')
        meta['current_page'] = current_page
        next_url = self.SEARCH_URL.format(search_term=st, page_num=current_page)
        return Request(url=next_url, meta=meta, cookies=self.cookies)
