from __future__ import division, absolute_import, unicode_literals

from .chegg import CheggProductsSpider
from scrapy.http import Request
import re
import json

class CheggShelfPagesSpider(CheggProductsSpider):
    name = 'chegg_shelf_urls_products'
    allowed_domains = ["www.chegg.com"]
    PRODUCTS_URL = "https://www.chegg.com/_ajax/federated/search?query={query}&search_data=%7B%22chgsec%22%3A%22searchsection%22%2C%22chgsubcomp%22%3A%22serp%22%2C%22state%22%3A%22NoState%22%2C%22profile%22%3A%22textbooks-srp%22%2C%22page-number%22%3A{page_number}%7D&token={token}"
    use_proxies = False

    def __init__(self, *args, **kwargs):
        if kwargs.get('quantity'):
            kwargs.pop('quantity')
        self.current_page = 1
        if "num_pages" in kwargs:
            self.num_pages = int(kwargs['num_pages'])
        else:
            self.num_pages = 1
        super(CheggShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}.copy()

    def start_requests(self):
        yield Request(url=self.product_url.replace("\'", ""),
                      meta=self._setup_meta_compatibility(),
                      callback=self._parse_helper)

    def _parse_helper(self, response):
        self.current_page = self.current_page + 1
        self.category_name = re.search('search/(.*?)/', response.url, re.DOTALL).group(1)
        self.token = re.search('csrfToken = (.*?);', response.body, re.DOTALL).group(1).replace("\'", "")
        return Request(self.PRODUCTS_URL.format(query=self.category_name, page_number=self.current_page, token=self.token),
                       meta=self._setup_meta_compatibility())

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        return super(CheggShelfPagesSpider, self)._scrape_next_results_page_link(response)

    def _scrape_total_matches(self, response):
        return None
