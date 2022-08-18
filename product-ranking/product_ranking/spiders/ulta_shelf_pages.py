# -*- coding: utf-8 -*-

import re
import sys

from scrapy import Request

from product_ranking.items import SiteProductItem

from .ulta import UltaProductSpider

is_empty = lambda x: x[0] if x else None


class UltaShelfPagesSpider(UltaProductSpider):
    name = 'ulta_shelf_urls_products'
    allowed_domains = ["ulta.com"]

    def _setup_class_compatibility(self):
        """ Needed to maintain compatibility with the SC spiders baseclass """
        self.quantity = sys.maxint
        self.site_name = self.allowed_domains[0]
        self.user_agent_key = None
        self.current_page = 1

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': sys.maxint, 'search_term': ''}.copy()

    def __init__(self, *args, **kwargs):
        super(UltaShelfPagesSpider, self).__init__(*args, **kwargs)
        self.product_url = kwargs['product_url']
        self._setup_class_compatibility()
        self.num_pages = int(kwargs.pop('num_pages', '1'))

        # variants are switched off by default, see Bugzilla 3982#c11
        self.scrape_variants_with_extra_requests = False
        if 'scrape_variants_with_extra_requests' in kwargs:
            scrape_variants_with_extra_requests = kwargs['scrape_variants_with_extra_requests']
            if scrape_variants_with_extra_requests in (1, '1', 'true', 'True', True):
                self.scrape_variants_with_extra_requests = True

    def start_requests(self):
        yield Request(url=self.valid_url(self.product_url),
                      meta=self._setup_meta_compatibility(),
                      dont_filter=True)

    @staticmethod
    def valid_url(url):
        if not re.findall("http(s){0,1}\:\/\/", url):
            url = "http://" + url
        return url

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//a[contains(@class, "product")][contains(@href, "productDetail.jsp")]'
            '/img/../@href').extract()
        if not links:
            links = response.xpath('//*[contains(@id, "search-prod")]'
                                   '//a[contains(@class, "product")]/@href').extract()
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        links = response.xpath('//li[contains(@class, "next-prev")]'
                               '//a[contains(text(), "Next")]/@href').extract()
        if links:
            return links[0]
