# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

import re
from scrapy.http import Request
from scrapy.log import INFO

from product_ranking.items import SiteProductItem
from product_ranking.utils import valid_url
from .osh import OshProductsSpider


class OshShelfPagesSpider(OshProductsSpider):
    name = 'osh_shelf_urls_products'
    allowed_domains = ["osh.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(OshShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      meta={'search_term': '', 'remaining': self.quantity})

    def _scrape_total_matches(self, response):
        totals = response.xpath('//li[@class="countsummary"]/span/text()').extract()
        if totals:
            totals = re.search('of (\d+)', totals[0])
            return int(totals.group(1)) if totals else 0

    def _scrape_product_links(self, response):
        """
        Scraping product links from shelf page
        """
        items = response.xpath('//div[@class="productList"]/ul/div[@class="product-item"]'
                               '/div[contains(@class, "producttitle")]/a/@href').extract()

        if items:
            for item in items:
                res_item = SiteProductItem()
                yield item, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return

        self.current_page += 1

        return super(OshShelfPagesSpider, self)._scrape_next_results_page_link(response)