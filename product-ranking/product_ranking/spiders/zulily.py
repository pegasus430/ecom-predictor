# -*- coding: utf-8 -*-
import string
import urllib
import urlparse
import re
import json
import time
from scrapy.utils.response import open_in_browser
from scrapy.log import DEBUG
from scrapy import FormRequest, Request, Spider
from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, cond_set, \
    FLOATING_POINT_RGEX, cond_set_value


class ZulilyProductsSpider(BaseProductsSpider):
    name = "zulily_products"
    allowed_domains = ["www.zulily.com"]

    LOG_IN_URL = "https://www.zulily.com/auth"
    SEARCH_URL = 'http://www.zulily.com/{search_term}?fromSearch=true&searchTerm={search_term}'
    use_proxies = True

    def __init__(self, *args, **kwargs):
        super(ZulilyProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)
        self.product_url = kwargs['product_url']

        self.login = kwargs.get("login", "arnoldmessi777@gmail.com")
        self.password = kwargs.get("password", "apple123")

    def start_requests(self):
        body = '{{"login": {{"username": "{email}", "password": "{password}"}}, ' \
               '"redirectUrl": "https://www.zulily.com/"}}'.format(email=self.login, password=self.password)

        yield Request(self.LOG_IN_URL,
                      method='POST',
                      body=body,
                      callback=self._log_in,
                      headers={'Content-Type': 'application/json;charset=UTF-8'})

    def _log_in(self, response):
        prod = SiteProductItem()
        prod['is_single_result'] = True
        prod['url'] = self.product_url
        prod['search_term'] = ''

        yield Request(self.product_url, callback=self._start_requests, meta={'product': prod})

    def _scrape_next_results_page_link(self, response):
        # <a role="button" class="right_arrow " id = "WC_SearchBasedNavigationResults_pagination_link_right_categoryResults" href = 'javascript:dojo.publish("showResultsForPageNumber",[{pageNumber:"2",pageSize:"60", linkId:"WC_SearchBasedNavigationResults_pagination_link_right_categoryResults"}])' title="Show next page"></a>
        # pageNumber:"2",pageSize:"60",
        next_page = response.xpath('//a[@class="right_arrow "]/@href').re('pageNumber:"(\d+)"')
        if next_page:
            next_page = int(next_page[0])
        else:
            return
        url = re.sub('pageNumber=\d+', 'pageNumber={}'.format(next_page), response.url)

    def _start_requests(self, response):
        """Generate Requests from the SEARCH_URL and the search terms."""
        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8'),),
                    page=1,
                    store_id=self.store_id
                ),
                meta={'search_term': st, 'remaining': self.quantity},
            )

        if self.product_url:
            yield self.parse_product(response)

    def extract_product_json(self, response):
        product_json = {"id_json": {}, "event_data": {}, "style_data": {}}

        try:
            id_json = response.xpath("//script[@type='application/ld+json']/text()").extract()[0].strip()
            product_json["id_json"] = json.loads(id_json)
        except Exception as e:
            self.log("Parsing issue in id_json.", DEBUG)

        try:
            event_data = re.findall(r'window.eventData =(.+);\n\twindow.styleData =', response.body_as_unicode())[0]
            product_json["event_data"] = json.loads(event_data)
        except Exception as e:
            self.log("Parsing issue in even_data.", DEBUG)

        try:
            style_data = re.findall(r'window.styleData =(.+);\n', response.body_as_unicode())[0]
            product_json["style_data"] = json.loads(style_data)
        except Exception as e:
            self.log("Parsing issue in style_data.", DEBUG)

        return product_json

    def parse_product(self, response):
        product = response.meta['product']

        # locale
        product['locale'] = 'en_US'

        product_json = self.extract_product_json(response)

        # title
        title = product_json.get("id_json", {}).get("name", None)
        cond_set_value(product, 'title', title)

        # categories
        categories = product_json.get("style_data", {}).get("categories", [])
        categories = [category_info["value"] for category_info in categories]

        if categories:
            cond_set_value(product, 'categories', categories)

        if product.get('categories'):
            product['category'] = product['categories'][-1]

        # description
        description = response.xpath("//div[@class='description']").extract()[0]
        cond_set_value(product, 'description', description)

        # price
        price = product_json.get("style_data", {}).get("price", None)
        cond_set_value(product, 'price', price)

        # image
        image = product_json.get("id_json", {}).get("image", None)
        if image:
            cond_set_value(product, 'image_url', image)

        # brand
        brand = product_json.get("id_json", {}).get("brand", {}).get("name", None)
        cond_set_value(product, "brand", brand)

        # original price
        original_price = product_json.get("style_data", {}).get("originalPrice", None)
        cond_set_value(product, 'price_original', original_price)

        # no longer available
        availability = response.xpath("//meta[@property='og:availability']/@content").extract()
        if availability:
            no_longer_avail = False if availability[0] == 'instock' else True
        cond_set_value(product, 'no_longer_available', no_longer_avail)
        if product['no_longer_available']:
            product['is_out_of_stock'] = True

        return product

    def _total_matches_from_html(self, response):
        total_matches = response.xpath("//div[@class='searchBanner control']/span/text()").re(r'\d+(?:,\d+)?')
        if total_matches:
            return int(total_matches[0].replace(",", ""))

    def _scrape_product_links(self, response):
        for link in response.xpath("//ul[contains(@class,'products-grid')]/li//a[contains(@class, 'product-image')]/@href").extract():
            yield link.split('?')[0], SiteProductItem()
