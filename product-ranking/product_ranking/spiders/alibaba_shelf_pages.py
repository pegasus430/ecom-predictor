# -*- coding: utf-8 -*-

import re
import json
import traceback

from .alibaba import AlibabaProductsSpider
from product_ranking.items import SiteProductItem
from scrapy.http import Request


class AlibabaShelfProductsSpider(AlibabaProductsSpider):
    name = 'alibaba_shelf_urls_products'
    allowed_domains = ["alibaba.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(AlibabaShelfProductsSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity}
                      )

    def _scrape_total_matches(self, response):
        total_matches = re.search(r'window.XPJAX_MAIN_DATA.util = (\{.*?\});', response.body)
        try:
            total_matches = json.loads(total_matches.group(1))
            return total_matches.get('num', '0')

        except:
            self.log('Error Parsing total_mathces: {}'.format(traceback.format_exc()))

    def _scrape_product_links(self, response):
        product_links = response.xpath('//div[contains(@id, "product")]'
                                       '//h2[@class="title"]/a/@href').extract()
        if not product_links:
            self.log('no product links: {}'.format(response.url))
            return list(super(AlibabaShelfProductsSpider, self)._scrape_product_links(response))

        return [(link, SiteProductItem()) for link in product_links]

    def _scrape_next_results_page_link(self, response):
        page_json = re.search(r'window.XPJAX_MAIN_DATA.pagination = (\{.*?\});', response.body, re.DOTALL)
        if not page_json:
            next_request = super(AlibabaShelfProductsSpider, self)._scrape_next_results_page_link(response)
            return next_request
        try:
            page_json = json.loads(page_json.group(1))
            current_page = page_json.get('current', 1)
            total_page = page_json.get('total', 0)
            if current_page < total_page and current_page < self.num_pages:
                current_page += 1
                next_url = page_json.get('urlRule', '').format(current_page)
                if next_url:
                    return Request(next_url, meta=response.meta, callback=self._parse_help)
        except:
            self.log('Error Parsing Pagination Json: {}'.format(traceback.format_exc()))

