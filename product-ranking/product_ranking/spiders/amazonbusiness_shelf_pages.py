from __future__ import division, absolute_import, unicode_literals

from .amazonbusiness import AmazonBusinessProductsSpider
from product_ranking.utils import valid_url
from product_ranking.items import SiteProductItem
from scrapy.http import Request
import traceback
import re


class AmazonBusinessShelfPagesSpider(AmazonBusinessProductsSpider):
    name = 'amazonbusiness_shelf_urls_products'
    allowed_domains = ["www.amazon.com"]

    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/60.0.3112.78 Safari/537.36"}

    def __init__(self, zip_code='94117', *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.zip_code = zip_code
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(AmazonBusinessShelfPagesSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def after_login(self, response):
        return Request(url=valid_url(self.product_url),
                       meta={'search_term': '', 'remaining': self.quantity},
                       headers=self.headers, dont_filter=True)

    def _scrape_total_matches(self, response):
        try:
            total_matches = response.xpath('//h2[@id="s-result-count"]/text()').re('(\d+) results')[0]
            if not total_matches:
                total_matches = re.search('(\d+) results for', response.body).group(1)
            return int(total_matches)
        except:
            self.log("Found no total matches {}".format(traceback.format_exc()))
            return 0

    def _scrape_results_per_page(self, response):
        item_count = response.xpath('//h2[@id="s-result-count"]/text()').extract()
        if item_count:
            item_count = re.findall('1-(\d+) of', item_count[0].strip())
            return int(item_count[0]) if item_count else None

    def _scrape_product_links(self, response):
        links = response.xpath('//li[contains(@id, "result_")]'
                               '//a[contains(@class, "s-access-detail-page")]/@href').extract()
        try:
            for link in links:
                yield link, SiteProductItem()
        except:
            self.log("Found no product links {}".format(traceback.format_exc()))

    def _scrape_next_results_page_link(self, response):
        if self.current_page < self.num_pages:
            self.current_page += 1
            return super(AmazonBusinessShelfPagesSpider,
                         self)._scrape_next_results_page_link(response)
