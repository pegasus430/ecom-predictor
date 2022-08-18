# -*- coding: utf-8 -*-

from .bjs import BJSProductsSpider
from scrapy.http import Request


class BjsShelfPagesSpider(BJSProductsSpider):
    name = 'bjs_shelf_urls_products'
    allowed_domains = ["www.bjs.com"]
    CATEGORY_URL = 'http://www.bjs.com/category?N={category_id}&No={page_nums}&Nrpp=120'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        self.category_id = None
        super(BjsShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        category_id = self.product_url.split('.')
        if len(category_id) > 1:
            category_id = category_id[-2]
            url = self.CATEGORY_URL.format(category_id=category_id, page_nums=0)
            self.category_id = category_id
            yield Request(url=url,
                          meta={'search_term': "", 'remaining': self.quantity},
                          )

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page')
        if not current_page:
            current_page = 1
        if current_page >= self.num_pages:
            return
        if current_page * 120 > self.total_matches:
            return
        next_page = current_page
        url = self.CATEGORY_URL.format(page_nums=next_page*120, category_id=self.category_id)
        return Request(
            url,
            meta={
                'search_term': "",
                'remaining': self.quantity,
                'current_page': next_page+1},)
