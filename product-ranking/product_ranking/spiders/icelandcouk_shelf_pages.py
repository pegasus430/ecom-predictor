# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
from scrapy import Request
from scrapy.log import INFO
from urlparse import urljoin
from product_ranking.utils import valid_url
from product_ranking.items import SiteProductItem

from product_ranking.spiders.icelandcouk import IcelandcoukProductsSpider


class IcelandcoukShelfPagesSpider(IcelandcoukProductsSpider):
    name = 'icelandcouk_shelf_urls_products'
    allowed_domains = ["iceland.co.uk"]

    def __init__(self, *args, **kwargs):
        self.product_url = kwargs['product_url']
        self.current_page = 1
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(IcelandcoukShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      meta={'remaining': self.quantity,
                            'search_term': ''})

    def _scrape_total_matches(self, response):
        total_matches = re.search('There are (\d+) items', response.body)
        other_total_matches = re.search('Showing all (\d+) product', response.body)
        if total_matches:
            total_matches = total_matches.group(1)
        elif other_total_matches:
            total_matches = other_total_matches.group(1)
        else:
            total_matches = 0

        return int(total_matches)

    def _scrape_product_links(self, response):
        links = response.xpath('//div[@class="product_info"]/h6/a/@href').extract()
        if links:
            for link in links:
                yield urljoin(response.url, link), SiteProductItem()
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1

        next_page_selector = response.xpath('//a[@class="nextPageUrl"]/@href').extract()
        if next_page_selector:
            return urljoin(response.url, next_page_selector[0])
