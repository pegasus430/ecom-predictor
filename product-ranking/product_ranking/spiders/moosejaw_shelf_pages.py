# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

from scrapy import Request

from product_ranking.items import SiteProductItem
from product_ranking.utils import valid_url

from .moosejaw import MoosejawProductsSpider

class MoosejawShelfPagesSpider(MoosejawProductsSpider):
    name = 'moosejaw_shelf_urls_products'
    allowed_domains = ["moosejaw.com"]

    def __init__(self, *args, **kwargs):
        self.current_page = 1
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(MoosejawShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      meta={'remaining': self.quantity,
                            'search_term': ''})

    def _scrape_product_links(self, response):
        links = response.xpath('//a[@class="prod-item__name cf"]/@href').extract()

        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return

        self.current_page += 1
        return super(MoosejawShelfPagesSpider, self)._scrape_next_results_page_link(response)