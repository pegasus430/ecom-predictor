# ~~coding=utf-8~~
from __future__ import division, absolute_import, unicode_literals

import re
from scrapy.http import Request
from scrapy.conf import settings
from .amazones import AmazonProductsSpider


class AmazonESShelfPagesSpider(AmazonProductsSpider):
    name = 'amazones_shelf_urls_products'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        self.num_pages = min(10, self.num_pages)
        super(AmazonESShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

        self.user_agent = 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        middlewares['scrapy.contrib.downloadermiddleware.redirect.MetaRefreshMiddleware'] = None

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}

    def start_requests(self):
        yield Request(
            url=self.product_url,
            meta=self._setup_meta_compatibility()
        )

    def _scrape_total_matches(self, response):
        totals = response.xpath('//*[contains(@id, "s-result-count")]/text()').extract()
        if totals:
            totals = re.search(self.total_matches_re, totals[0].replace(',', ''))
            return int(totals.group(1)) if totals else 0

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return

        self.current_page += 1

        return super(AmazonESShelfPagesSpider, self)._scrape_next_results_page_link(response)
