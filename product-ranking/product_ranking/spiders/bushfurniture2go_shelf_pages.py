# -*- coding: utf-8 -*-

from scrapy.http import Request
from .bushfurniture2go import BushFurniture2goProductSpider


class BushFurniture2goShelfPagesSpider(BushFurniture2goProductSpider):
    name = 'bushfurniture2go_shelf_urls_products'
    allowed_domains = ["www.bushfurniture2go.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(BushFurniture2goShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity})

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        current_page = meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return
        current_page += 1
        meta['current_page'] = current_page
        next_link = super(BushFurniture2goShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)

        return Request(
            url=next_link,
            meta=meta
        ) if next_link else None
