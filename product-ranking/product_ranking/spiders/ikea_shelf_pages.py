# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import urlparse

from scrapy import Request
from scrapy.log import INFO

from product_ranking.items import SiteProductItem

from .ikea import IkeaProductsSpider


class IkeaShelfPagesSpider(IkeaProductsSpider):
    name = 'ikea_shelf_urls_products'
    allowed_domains = ["ikea.com", "www.ikea.com"]

    def __init__(self, *args, **kwargs):
        super(IkeaShelfPagesSpider, self).__init__(*args, **kwargs)
        self.product_url = kwargs['product_url']

    @staticmethod
    def valid_url(url):
        if not re.findall(r"http(s){0,1}\:\/\/", url):
            url = "http://" + url
        return url

    def start_requests(self):
        yield Request(url=self.valid_url(self.product_url),
                      meta={'remaining': self.quantity,
                            'search_term': ''})

    def _scrape_product_links(self, response):
        items = response.xpath(
            '//div[contains(@id,"item_")]//'
            'a[@class="productLink"]/@href').extract()

        if items:
            for item in items:
                link = urlparse.urljoin(response.url, item)
                res_item = SiteProductItem()
                yield link, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        # Ikea shelf pages doesnt have pagination
        return

    def parse_product(self, response):
        return super(IkeaShelfPagesSpider, self).parse_product(response)

    def _scrape_total_matches(self, response):
        total_matches = re.search(r'prodLength\s?=\s?[\'\"](\d+)[\'\"]', response.body_as_unicode())
        total_matches = int(total_matches.group(1)) if total_matches else 0
        return total_matches

    def _scrape_results_per_page(self, response):
        return self._scrape_total_matches(response)
