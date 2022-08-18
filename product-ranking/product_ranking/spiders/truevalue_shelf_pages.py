# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

from .truevalue import TruevalueProductsSpider
from scrapy.http import Request
from scrapy.log import INFO
from urlparse import urljoin
import re
import traceback

from product_ranking.items import SiteProductItem
from product_ranking.utils import valid_url


class TrueValueShelfPagesSpider(TruevalueProductsSpider):
    name = 'truevalue_shelf_urls_products'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(TrueValueShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      meta={'search_term': '', 'remaining': self.quantity})

    def _scrape_total_matches(self, response):
        totals = re.search('"totalItems":(.*?),', response.body)
        return int(totals.group(1)) if totals else None

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//a[@class="prdBrandModel"]/@href').extract()

        if items:
            for item in items:
                link = urljoin('http://www.truevalue.com', item)
                res_item = SiteProductItem()
                yield link, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return

        self.current_page += 1
        return super(TrueValueShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)