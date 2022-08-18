# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import re

from scrapy import Request

from product_ranking.spiders.target import TargetProductSpider


class TargetShelfPagesSpider(TargetProductSpider):
    name = 'target_shelf_urls_products'
    allowed_domains = ["target.com", "recs.richrelevance.com",
                       'api.bazaarvoice.com']
    SEARCH_URL = "http://redsky.target.com/v1/plp/search?count=24&offset=0&category={category}"

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(TargetShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        searched = re.search('^https?://[\w]*\.target\.com/[\w\/-]+/-/N-(\w+?)Z(\w+)#?', self.product_url)
        if not searched:
            searched = re.search('^https?://[\w]*\.target\.com/[\w\/-]+/-/N-(\w+)#?', self.product_url)
        if searched:
            yield Request(url=self.SEARCH_URL.format(category=searched.group(1)),
                          meta={'remaining': self.quantity, 'search_term': ''},
                          dont_filter=True)

    def _scrape_next_results_page_link(self, response):
        if self.current_page < self.num_pages:
            self.current_page += 1
            return super(TargetShelfPagesSpider,
                        self)._scrape_next_results_page_link(response)
