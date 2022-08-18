# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import json
import math
import urlparse
import traceback
from scrapy.http import Request
from scrapy.log import INFO
from product_ranking.items import SiteProductItem
from .redmart_mobile import RedmartMobileProductsSpider


class RedmartMobileShelfPagesSpider(RedmartMobileProductsSpider):
    name = 'redmart_mobile_shelf_urls_products'
    CATEGORY_API_URL = "https://api.redmart.com/v1.6.0/catalog/search?" \
                       "pageSize=18&sort=1024&category={category_name}&page={page_num}"

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', 1))
        super(RedmartMobileShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        category_name = urlparse.urlparse(self.product_url).path.split('/')
        if len(category_name) >= 1:
            category_name = category_name[-1]
            yield Request(url=self.CATEGORY_API_URL.format(category_name=category_name,
                                                           page_num=0),
                          meta={'remaining': self.quantity,
                                'search_term': '',
                                'category_name': category_name})
        else:
            self.log("Found no category name {}".format(traceback))

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        try:
            data = json.loads(response.body_as_unicode())
            items = data.get('products', [])

            for item in items:
                res_item = SiteProductItem()
                link = self.PRODUCT_API_URL.format(item.get('details', {}).get('uri'))
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
            results_per_page = 18
        if (total_matches and results_per_page
            and current_page < math.ceil(total_matches / float(results_per_page))):
            current_page += 1
            response.meta['current_page'] = current_page
            return Request(self.CATEGORY_API_URL.format(category_name=response.meta['category_name'],
                                                        page_num=current_page - 1),
                           meta=response.meta,
                           dont_filter=True)
