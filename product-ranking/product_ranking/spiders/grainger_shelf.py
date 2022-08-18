# -*- coding: utf-8 -*-

import urlparse
import re

from .grainger import GraingerProductsSpider
from scrapy.http import Request
from product_ranking.utils import is_empty


class GraingerShelfPagesSpider(GraingerProductsSpider):
    name = 'grainger_shelf_urls_products'
    allowed_domains = ["www.grainger.com"]
    SHELF_NEXT_PAGE_PARAM = '?perPage={results_per_page}&requestedPage={page_num}'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        self.current_page = 0
        super(GraingerShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      )

    def _scrape_next_results_page_link(self, response):
        next_page_link = None
        page_param = None

        results_per_page = is_empty(response.xpath("//span[@class='itemsPerPage']//span/text()").extract())
        self.current_page += 1
        if results_per_page:
            page_param = self.SHELF_NEXT_PAGE_PARAM.format(results_per_page=results_per_page, page_num=self.current_page)

        next_page = is_empty(response.xpath("//li[@class='next']//a/@onclick").extract())
        if next_page:
            next_page = re.search('(.*?)\);', next_page.split(',')[-1])
            if next_page and page_param:
                next_page_link = urlparse.urljoin(response.url, next_page.group(1).replace("\'", "") + page_param)

        if next_page_link:
            return next_page_link