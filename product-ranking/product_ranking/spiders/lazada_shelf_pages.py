# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import json
import math
import traceback
from scrapy.http import Request
from scrapy.log import INFO
from product_ranking.items import SiteProductItem
from .lazada import LazadaProductsSpider


class LazadaShelfPagesSpider(LazadaProductsSpider):
    name = 'lazadasg_shelf_urls_products'
    CATEGORY_URL = "https://www.lazada.sg/{category}/" \
                   "?ajax=true&page={page_num}&spm={spm}"

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', 1))
        super(LazadaShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        category = re.search('lazada.sg/(.*)/\?', self.product_url)
        spm = re.search('spm=(.*)', self.product_url)
        if category and spm:
            yield Request(url=self.CATEGORY_URL.format(category=category.group(1),
                                                       spm=spm.group(1),
                                                       page_num=1),
                          meta={'remaining': self.quantity,
                                'search_term': '',
                                'category': category.group(1),
                                'spm': spm.group(1)})
        else:
            self.log("Found no category or spm {}".format(traceback.format_exc()))

    def _scrape_total_matches(self, response):
        try:
            shelf_data = json.loads(response.body_as_unicode())
            totals = shelf_data.get('mainInfo', {}).get('dataLayer', {}).get('page', {}).get('resultNr')
            return int(totals)
        except:
            self.log("Found no total_matches {}".format(traceback.format_exc()))
            return 0

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        try:
            shelf_data = json.loads(response.body_as_unicode())
            items = shelf_data.get('mods', {}).get('listItems')

            if items:
                for item in items:
                    res_item = SiteProductItem()
                    link = item.get('productUrl')
                    yield link, res_item
        except:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page')
        if not current_page:
            current_page = 1
        if current_page >= self.num_pages:
            return

        total_matches = response.meta.get('total_matches')
        results_per_page = self._scrape_results_per_page(response)
        if not results_per_page:
            results_per_page = 40

        if (total_matches and results_per_page
            and current_page < math.ceil(total_matches / float(results_per_page))):

            current_page += 1
            response.meta['current_page'] = current_page
            next_link = self.CATEGORY_URL.format(category=response.meta['category'],
                                                 spm=response.meta['spm'],
                                                 page_num=current_page)
            return Request(url=next_link, meta=response.meta)
