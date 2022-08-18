from __future__ import division, absolute_import, unicode_literals

from .boxed import BoxedProductsSpider
from scrapy.http import Request
from urlparse import urljoin
import json


class BoxedShelfPagesSpider(BoxedProductsSpider):
    name = 'boxed_shelf_urls_products'
    allowed_domains = ["www.boxed.com"]
    payload = 'categoryPayload'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(BoxedShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}.copy()

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta=self._setup_meta_compatibility(),
                      headers=self._get_api_headers())

    def _scrape_next_results_page_link(self, response):
        try:
            if self.current_page < self.num_pages:
                self.current_page += 1

                data = json.loads(response.body)

                next_url = '/api{}'.format(data['data'][self.payload]['pagination']['paginationApiUrl'])

                return Request(urljoin(response.url, next_url),
                               headers=self._get_api_headers(),
                               meta=dict(response.meta),
                               priority=1)
        except:
            return None