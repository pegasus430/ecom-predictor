# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

from .treehouse import TreeHouseProductsSpider
from scrapy.http import Request
import urlparse

from scrapy.log import INFO
from product_ranking.items import SiteProductItem
from product_ranking.utils import valid_url


class TreeHouseShelfPagesSpider(TreeHouseProductsSpider):
    name = 'treehouse_shelf_urls_products'
    allowed_domains = ['tree.house']

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(TreeHouseShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      meta={'search_term': '', 'remaining': self.quantity})

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//div[contains(@class, "product-grid-item")]//a[@class="grid-image"]/@href'
            ).extract()

        if links:
            for link in links:
                link = urlparse.urljoin(response.url, link)
                yield link, SiteProductItem()
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        return None