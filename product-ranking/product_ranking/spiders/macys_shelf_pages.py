# -*- coding: utf-8 -*-
from .macys import MacysProductsSpider
from scrapy import Request
from product_ranking.utils import replace_http_with_https


class MacysShelfPagesSpider(MacysProductsSpider):
    name = 'macys_shelf_urls_products'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(MacysShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        meta = {'search_term': "", 'remaining': self.quantity}
        cookies = {'shippingCountry': 'US'}
        self.product_url = replace_http_with_https(self.product_url).replace('https://www1.', 'https://www.')
        yield Request(url=self.product_url, meta=meta, cookies=cookies)

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        return super(MacysShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)
