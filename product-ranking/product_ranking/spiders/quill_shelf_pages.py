# -*- coding: utf-8 -*-

from .quill import QuillProductsSpider
from scrapy.http import Request
import time
import re

class QuillShelfPagesSpider(QuillProductsSpider):
    name = 'quill_shelf_urls_products'
    allowed_domains = ["www.quill.com"]
    CATEGORY_URL = 'https://www.quill.com/SearchEngine/GetSearchResults?keywords=&filter=0&' \
                   'sortOption=BestMatch&browseType=SS&browseID={category_id}&ShowSkuSetsData=False&_={begin_index}'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        self.category_id = None
        self.begin_index = None
        super(QuillShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        self.begin_index = int(round(time.time() * 1000))
        category_id = self.product_url.split('.')

        if len(category_id) > 1:
            category_id = re.search('(\d+)', category_id[-2], re.DOTALL)
            if category_id:
                category_id = category_id.group(1)

            self.category_id = category_id
            yield Request(url=self.product_url,
                          meta={'search_term': "", 'remaining': self.quantity},
                          )

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page')

        total_matches = response.meta.get('total_matches', 0)

        if not current_page:
            current_page = 0
        if current_page * 24 > total_matches:
            return
        current_page += 1
        next_page = self.begin_index + current_page
        url = self.CATEGORY_URL.format(begin_index=next_page, category_id=self.category_id)
        return Request(
            url,
            meta={
                'search_term': "",
                'remaining': self.quantity,
                'current_page': current_page,
            }, )