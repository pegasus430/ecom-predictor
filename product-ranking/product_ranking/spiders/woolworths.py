from __future__ import absolute_import, division, unicode_literals

import json
import re
import traceback

from scrapy.log import WARNING

from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider, FormatterWithDefaults,
                                     cond_set_value)
from product_ranking.validation import BaseValidator


class WoolworthsProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'woolworths_products'
    allowed_domains = ["www.woolworths.com.au"]

    SEARCH_URL = "https://www.woolworths.com.au/apis/ui/Search/products" \
                 "?IsSpecial=false&PageNumber={page_number}&PageSize=24&SearchTerm={search_term}&SortType=TraderRelevance"
    JSON_PRODUCT_URL = "https://www.woolworths.com.au/apis/ui/product/detail/{product_id}?validateUrl=false"
    PRODUCT_URL = 'https://www.woolworths.com.au/Shop/ProductDetails/{stockcode}/{name}'

    def __init__(self, *args, **kwargs):
        self.current_page = 1

        super(WoolworthsProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            url_formatter=FormatterWithDefaults(page_number=self.current_page),
            *args,
            **kwargs)

        self.searchterms = [search_term.replace('\'', '') for search_term in self.searchterms]
        if self.product_url:
            product_id = re.search(r'productId=(\d+)', self.product_url)
            if not product_id:
                product_id = re.search(r'/productdetails/(\d+)/', self.product_url.lower())
            if product_id:
                product_id = product_id.group(1)
                self.product_url = self.JSON_PRODUCT_URL.format(product_id=product_id)
        self.total_matches_field_name = "SearchResultsCount"
        self.product_links_field_name = "Products"

    def _scrape_total_matches(self, response):
        try:
            search_product_json = json.loads(response.body_as_unicode())
            total_matches = search_product_json.get(self.total_matches_field_name, 0)
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
            total_matches = 0
        return int(total_matches)

    def _scrape_product_links(self, response):
        try:
            search_product_json = json.loads(response.body_as_unicode())
        except:
            self.log('Can not parse json: {}'.format(traceback.format_exc()))
        else:
            products = search_product_json.get(self.product_links_field_name)
            if products:
                for product in products:
                    response.meta['product'] = SiteProductItem()
                    item = self.parse_product(response, {'Product': product['Products'][0]})
                    yield None, item

    def _scrape_next_results_page_link(self, response):
        if self.quantity - response.meta['remaining'] < self._scrape_total_matches(response):
            self.current_page += 1
            return self.SEARCH_URL.format(search_term=response.meta['search_term'],
                                          page_number=self.current_page)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response, product_json=None):
        # if we can not parse json here it is ok, that exception is raised
        product_json = product_json or json.loads(response.body_as_unicode())

        product = response.meta['product']
        product['locale'] = "en-US"

        # For woolworths.com.au, this flag should always be "NULL", which would represent that there is no information to report on
        product['in_store_pickup'] = None

        title = product_json['Product']['Name']
        cond_set_value(product, 'title', title)

        model = product_json['Product']['Stockcode']
        product['model'] = model

        product['reseller_id'] = model

        brand = product_json['Product']['Brand']
        cond_set_value(product, 'brand', brand)

        image_url = product_json['Product']['LargeImageFile']
        cond_set_value(product, 'image_url', image_url)

        price = product_json['Product']['Price']
        if price:
            price = Price(price=price, priceCurrency="USD")
            cond_set_value(product, 'price', price)

        description = product_json['Product']['RichDescription']
        product['description'] = description

        name = product_json['Product']['UrlFriendlyName']
        url = self.PRODUCT_URL.format(stockcode=model, name=name)
        product['url'] = url

        return product
