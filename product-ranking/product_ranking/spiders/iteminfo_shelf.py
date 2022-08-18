# -*- coding: utf-8 -*-

from .iteminfo import IteminfoProductsSpider
from scrapy.http import Request
from urlparse import urlparse

class IteminfoShelfPagesSpider(IteminfoProductsSpider):
    name = 'iteminfo_shelf_urls_products'
    allowed_domains = ["www.iteminfo.com"]
    CATEGORY_URL = 'http://www.iteminfo.com/search/{category_string}/ps_12/pg_{page_num}/so_ts'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        self.category_string = None
        super(IteminfoShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        category_string = urlparse(self.product_url).path.split('/')[-1]
        url = self.CATEGORY_URL.format(category_string=category_string, page_num=1)
        self.category_string = category_string
        yield Request(url=url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      dont_filter=True
                      )

    def _get_products(self, response):
        for request in super(IteminfoShelfPagesSpider, self)._get_products(response):
            request = request.replace(dont_filter=True)
            yield request

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        current_page = meta.get('current_page')
        if not current_page:
            current_page = 1
        if current_page >= self.num_pages:
            return
        if current_page * 12 > self.total_matches:
            return
        current_page += 1
        url = self.CATEGORY_URL.format(page_num=current_page, category_string=self.category_string)
        meta['current_page'] = current_page
        return Request(
            url,
            meta=meta,)
