# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

import re
import json
from scrapy.http import Request
from scrapy.log import INFO
import traceback

from product_ranking.items import SiteProductItem
from product_ranking.utils import valid_url
from .jcpenney import JcpenneyProductsSpider


class JCPenneyShelfPagesSpider(JcpenneyProductsSpider):
    name = 'jcpenney_shelf_urls_products'
    allowed_domains = ["jcpenney.com"]
    CATEGORY_API_URL = "https://search-api.jcpenney.com/v1{url_info}"

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(JCPenneyShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      callback=self._start_requests)

    def _start_requests(self, response):
        url_info = re.search('jcpenney.com(.*)', response.url)
        if url_info:
            yield Request(url=self.CATEGORY_API_URL.format(url_info=url_info.group(1)),
                          meta={'search_term': '', 'remaining': self.quantity})
        else:
            self.log("Found no category info {}".format(traceback.format_exc()))

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            totals = data.get('organicZoneInfo', {}).get('totalNumRecs')
            return totals
        except:
            self.log("Found no total_matches {}".format(traceback.format_exc()))
            return 0

    def _scrape_product_links(self, response):
        """
        Scraping product links from shelf page
        """
        try:
            data = json.loads(response.body_as_unicode())
            items = data.get('organicZoneInfo', {}).get('products', [])
            if items:
                for item in items:
                    res_item = SiteProductItem()
                    link = "https://www.jcpenney.com" + item.get('pdpUrl')
                    yield link, res_item
        except:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return

        current_page += 1

        try:
            data = json.loads(response.body_as_unicode())
            link = data.get('seoTitleTags', {}).get('nextUrl')
            next_link = self.CATEGORY_API_URL.format(url_info=link)
            return Request(next_link, meta=response.meta)
        except:
            self.log("Found no next link {}".format(traceback.format_exc()))
            return None

