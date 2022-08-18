# -*- coding: utf-8 -*-#

from __future__ import absolute_import, division, unicode_literals

import re
import urlparse
from urllib import urlencode

from scrapy.http import Request
from product_ranking.utils import valid_url
from product_ranking.spiders.heb import HebProductsSpider


class HebShelfPagesSpider(HebProductsSpider):
    name = 'heb_shelf_urls_products'
    allowed_domains = ["www.heb.com", "heb.com"]

    results_per_page = 35

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(HebShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      meta={'remaining': self.quantity,
                            'search_term': ''},
                      callback=self._parse_help)

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        current_page = meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return
        current_page += 1
        meta['current_page'] = current_page
        offset = (current_page - 1) * self.results_per_page
        find = re.search(r'No=\d+', response.url)
        if find:
            next_url = re.sub(r'No=\d+', 'No={}'.format(offset), response.url)
        else:
            url_parts = list(urlparse.urlparse(response.url))
            query_params = dict(urlparse.parse_qsl(url_parts[4]))
            query_params.update({'No': 35, 'Nrpp': 35})
            url_parts[4] = urlencode(query_params)
            next_url = urlparse.urlunparse(url_parts)
        request = super(HebShelfPagesSpider, self)._scrape_next_results_page_link(response)
        return request.replace(url=next_url) if request else None