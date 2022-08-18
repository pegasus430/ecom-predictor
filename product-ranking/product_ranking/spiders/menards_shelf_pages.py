# -*- coding: utf-8 -*-

from .menards import MenardsProductsSpider
from scrapy.http import Request
from urlparse import urljoin


class MenardsShelfPagesSpider(MenardsProductsSpider):
    name = 'menards_shelf_urls_products'
    allowed_domains = ["menards.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(MenardsShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      )

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        current_page = meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return
        current_page += 1
        meta['current_page'] = current_page
        next_link = response.xpath('//a[@class="fa fa-chevron-right"]/@href').extract()
        if next_link:
            return Request(
                urljoin(response.url, next_link[0]),
                meta=meta
            )
