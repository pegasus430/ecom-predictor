# -*- coding: utf-8 -*-#

import re
import json
import urllib

from scrapy.http import Request
from .jet import JetProductsSpider


class JetShelfPagesSpider(JetProductsSpider):
    name = 'jet_shelf_urls_products'
    allowed_domains = ['jet.com', 'powerreviews.com']

    def __init__(self, sort_mode=None, *args, **kwargs):
        super(JetShelfPagesSpider, self).__init__(*args, **kwargs)
        self.num_pages = int(kwargs.get('num_pages', 1))
        self.quantity = self.num_pages * 24

    def start_requests_with_csrf(self, response):
        csrf = self.get_csrf(response)
        api_key = self._get_api_key(response)
        st = response.meta.get('search_term')
        if self.product_url:
            body = self.construct_post_body()
            yield Request(
                url=self.SEARCH_URL,
                method="POST",
                body=body,
                meta={
                    'search_term': st,
                    'remaining': self.quantity,
                    'csrf': csrf,
                    'api_key': api_key
                },
                dont_filter=True,
                headers={
                    "content-type": "application/json",
                    "x-csrf-token": csrf,
                    "X-Requested-With":"XMLHttpRequest",
                    "jet-referer":"/search?term={}".format(st),

                },
            )

    def construct_post_body(self):
        # Helper func to construct post params for request
        category_id = re.findall(r"category=(\d+)", self.product_url)
        if not category_id:
            category_id = re.findall(r"\w\/(\d+)\b", self.product_url)
        category_id = category_id[0] if category_id else None

        searchterm = re.findall("term=([\w\s]+)", urllib.unquote(self.product_url).decode('utf8'))
        searchterm = searchterm[0] if searchterm else None

        if searchterm and not category_id:
            body = json.dumps({"term": searchterm, "origination": "none",
                               "sort": self.sort, "page": self.current_page})
        elif category_id and not searchterm:
            body = json.dumps({"categories": category_id, "origination": "PLP",
                               "sort": self.sort, "page": self.current_page})
        else:
            body = json.dumps({"term": searchterm, "categories": category_id,
                               "origination": "PLP", "sort": self.sort, "page": self.current_page})
        return body

    def _scrape_next_results_page_link(self, response):
        csrf = self.get_csrf(response) or response.meta.get("csrf")
        api_key = response.meta.get('api_key') or self._get_api_key(response)
        st = response.meta.get("search_term")
        if self.current_page >= self.num_pages:
            return None
        self.current_page += 1
        body = self.construct_post_body()
        return Request(
            url=self.SEARCH_URL,
            method="POST",
            body=body,
            meta={
                'search_term': st,
                'csrf': csrf,
                'total_matches': response.meta.get('total_matches'),
                'api_key': api_key
            },
            dont_filter=True,
            headers={
                "content-type": "application/json",
                "x-csrf-token": csrf,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
