# -*- coding: utf-8 -*-

from .buybuybaby import BuybuybabyProductsSpider
from scrapy.http import Request
from product_ranking.items import SiteProductItem
import re
import urlparse


class BuybuybabyShelfPagesSpider(BuybuybabyProductsSpider):
    name = 'buybuybaby_shelf_urls_products'
    allowed_domains = ["www.buybuybaby.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(BuybuybabyShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      )

    def _scrape_product_links(self, response):
        item_urls = response.xpath('//div[@class="prodName"]/a/@href').extract()
        for item_url in item_urls:
            yield urlparse.urljoin(response.url, item_url), SiteProductItem()

    def _scrape_total_matches(self, response):
        matches = response.xpath('//span[@id="allCount"]/text()').re('\d+')
        if matches:
            return int(matches[0])

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return
        if current_page * 48 > self._scrape_total_matches(response):
            return
        next_page = current_page + 1
        url = self.product_url + "{}-48".format(next_page)
        return Request(
            url,
            meta={
                'search_term': "",
                'remaining': self.quantity,
                'current_page': next_page},)
