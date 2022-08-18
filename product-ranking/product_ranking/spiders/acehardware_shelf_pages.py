# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

from .acehardware import AcehardwareProductsSpider
from scrapy.http import Request
from scrapy.log import INFO
import urlparse
import re

from product_ranking.items import SiteProductItem
from product_ranking.utils import valid_url


class AcehardwareShelfPagesSpider(AcehardwareProductsSpider):
    name = 'acehardware_shelf_urls_products'

    NEXT_PAGE_URL = "http://www.acehardware.com/family/index.jsp?" \
                    "page={page_num}&categoryId={category_id}"

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(AcehardwareShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      meta={'search_term': '', 'remaining': self.quantity})

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//ol[contains(@id, "products")]'
                               '/li//div[@class="details"]'
                               '//a[contains(@class, "titleLink")]/@href').extract()

        if items:
            for item in items:
                link = urlparse.urljoin(response.url, item)
                res_item = SiteProductItem()
                yield link, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):

        if self.current_page >= self.num_pages:
            return

        self.current_page += 1

        category_id = response.xpath('//div[@id="crumbs"]/span[@class="bredCrumbLabel"]'
                                     '/a/@href').extract()
        if category_id:
            category_id = re.search('categoryId=(\d+)', category_id[0], re.DOTALL)
            category_id = category_id.group(1) if category_id else None
            next_link = self.NEXT_PAGE_URL.format(page_num=self.current_page, category_id=category_id)

            return next_link