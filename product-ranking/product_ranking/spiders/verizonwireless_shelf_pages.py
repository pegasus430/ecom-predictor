# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, unicode_literals
import re
import urlparse

from scrapy.http import Request
import json

from product_ranking.items import SiteProductItem

is_empty = lambda x: x[0] if x else None

from .verizonwireless import VerizonwirelessProductsSpider


class VerizonwirelessShelfPagesSpider(VerizonwirelessProductsSpider):
    name = 'verizonwireless_shelf_urls_products'
    allowed_domains = ["verizonwireless.com", "api.bazaarvoice.com"]  # without this find_spiders() fails

    def _setup_class_compatibility(self):
        """ Needed to maintain compatibility with the SC spiders baseclass """
        self.quantity = 99999
        self.site_name = self.allowed_domains[0]
        self.user_agent_key = None
        self.zip_code = '12345'
        self.current_page = 1

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': 99999, 'search_term': ''}.copy()

    def __init__(self, *args, **kwargs):
        super(VerizonwirelessShelfPagesSpider, self).__init__(*args, **kwargs)
        self._setup_class_compatibility()

        self.product_url = kwargs['product_url']

        if "num_pages" in kwargs:
            self.num_pages = int(kwargs['num_pages'])
        else:
            self.num_pages = 1  # See https://bugzilla.contentanalyticsinc.com/show_bug.cgi?id=3313#c0

        self.user_agent = "Mozilla/5.0 (X11; Linux i686 (x86_64))" \
            " AppleWebKit/537.36 (KHTML, like Gecko)" \
            " Chrome/37.0.2062.120 Safari/537.36"

        # variants are switched off by default, see Bugzilla 3982#c11
        self.scrape_variants_with_extra_requests = False
        if 'scrape_variants_with_extra_requests' in kwargs:
            scrape_variants_with_extra_requests = kwargs['scrape_variants_with_extra_requests']
            if scrape_variants_with_extra_requests in (1, '1', 'true', 'True', True):
                self.scrape_variants_with_extra_requests = True

    @staticmethod
    def valid_url(url):
        if not re.findall("http(s){0,1}\:\/\/", url):
            url = "http://" + url
        return url

    def start_requests(self):
        yield Request(url=self.valid_url(self.product_url),
                      meta=self._setup_meta_compatibility())  # meta is for SC baseclass compatibility

    def _total_matches_from_html(self, response):
        total = response.xpath(
            ".//*[@id='filter-selections']/strong/text()").re('\d+')
        if not total:
            total = response.xpath(".//*[@id='c-breadbox']/strong/text()").re('\d+')
        total = int(total[0]) if total else 0
        if not total:
            try:
                js_script = response.xpath('.//script[@id="serviceContentId"]/text()').re(r'=\s(\{.+)\;')
                if js_script:
                    js_data = js_script[0]
                    js_data = json.loads(js_data)
                    total = js_data['gridwallContent']['results']['totalNumRecs']
            except BaseException:
                total = 0
        return total if total else 0

    def _scrape_product_links(self, response):
        urls = response.xpath('//h6[@class="fontsz_sub2 bold color_red"]/a/@href').extract()
        if not urls:
            urls = response.xpath('//h6[@class="gridwallTile_deviceName"]/a/@href').extract()
        if not urls:
            try:
                js_script = response.xpath('.//script[@id="serviceContentId"]/text()').re(r'=\s(\{.+)\;')
                if js_script:
                    js_data = js_script[0]
                    js_data = json.loads(js_data)
                    devices = js_data['gridwallContent']['results']['devices']
                    urls = [d['attributes']['product.pdpUrl'][0] for d in devices]
            except BaseException:
                urls = []

        urls = [urlparse.urljoin(response.url, x) for x in urls] if urls else []

        shelf_categories = response.xpath('//div[@id="breadCrumbHeader"]/ul/li/a/text() |'
        '//div[@id="breadCrumbHeader"]/ul/li/span/text()').extract()
        shelf_category = response.xpath('//h1/text()').extract()[0].strip()

        for url in urls:
            item = SiteProductItem()
            if shelf_category:
                item['shelf_name'] = shelf_category
            if shelf_categories:
                item['shelf_path'] = shelf_categories
            yield url, item

    def _scrape_next_results_page_link(self, response):
        # in case we want to scrape more pages than exist
        total = self._total_matches_from_html(response)
        perpage = self._scrape_results_per_page(response)
        if self.current_page == 1 and total and perpage:
            if self.num_pages * perpage > total:
                if perpage == total:
                    self.num_pages = 1
                else:
                    self.num_pages = int(total/perpage) + 1
        if self.current_page >= int(self.num_pages):
            return None
        else:
            self.current_page += 1
            next_link = response.xpath('.//*[@id="pageNav"]/a/*[@ class="next"]/../@href').extract()
            next_link = next_link[0] if next_link else None
            if not next_link:
                next_link = response.xpath('.//*[@class="page-link next"]/@href').extract()
                next_link = next_link[0] if next_link else None
            if not next_link:
                # looks like we got js-heavy version lets build pagination url prom json on page
                js_script = response.xpath('.//*[contains(text(), "var vzwDL =")]/text()').re(r'=\s(\{.+)\;')
                if js_script:
                    js_data = js_script[0]
                    js_data = json.loads(js_data)['page']
                    platform = js_data['platform']
                    condition = js_data['condition']
                    page_type = js_data['pageType']
                    section2 = js_data['section2']
                    next_link = 'page-{page}/?platform={platform}&' \
                                'condition={condition}&pageType={page_type}' \
                                '&section2={section2}'.format(
                        page=self.current_page,
                        platform=platform,
                        condition=condition,
                        page_type=page_type,
                        section2=section2,
                        )
            return urlparse.urljoin(response.url, next_link)

    def _scrape_results_per_page(self, response):
        res_perpage = len(list(self._scrape_product_links(response)))
        if res_perpage:
            return res_perpage
        else:
            return 0

    def parse_product(self, response):
        return super(VerizonwirelessShelfPagesSpider, self).parse_product(response)
