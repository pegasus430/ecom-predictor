# -*- coding: utf-8 -*-

from product_ranking.spiders.bloomingdales import BloomingDalesProductsSpider
from scrapy.http import Request


class BloomingDalesShelfProductsSpider(BloomingDalesProductsSpider):
    name = 'bloomingdales_shelf_urls_products'
    allowed_domains = ["bloomingdales.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(BloomingDalesShelfProductsSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      headers=self.headers,
                      dont_filter=True,
                      cookies=self.cookies
                      )

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        current_page = meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return
        current_page += 1
        meta['current_page'] = current_page
        request = super(BloomingDalesShelfProductsSpider, self)._scrape_next_results_page_link(response)
        if request:
            return request.replace(meta=meta, headers=self.headers)
