from __future__ import absolute_import, division, unicode_literals

import math
import urlparse

from scrapy.http import Request

from product_ranking.spiders.samsclub import SamsclubProductsSpider


class SamsclubShelfPagesSpider(SamsclubProductsSpider):
    name = 'samsclub_shelf_urls_products'
    allowed_domains = ["samsclub.com", "api.bazaarvoice.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        super(SamsclubShelfPagesSpider, self).__init__(clubno='4704', zip_code='94117', *args, **kwargs)
        self.prods_per_page = 48
        if "num_pages" in kwargs:
            self.num_pages = int(kwargs['num_pages'])
        else:
            self.num_pages = 1  # See https://bugzilla.contentanalyticsinc.com/show_bug.cgi?id=3313#c0
        self.current_page = 1

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}.copy()

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta=self._setup_meta_compatibility(),
                      headers=self.HEADERS)

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        pages = math.ceil(self._scrape_total_matches(response) / float(self.prods_per_page))
        if self.current_page <= pages:
            return self._set_next_results_page_url()

    def _get_next_products_page(self, response, prods_found):
        return super(SamsclubProductsSpider, self)._get_next_products_page(response, prods_found)

    def _set_next_results_page_url(self):
        scheme, netloc, path, query_string, fragment = urlparse.urlsplit(self.product_url)
        query_string = 'offset={}&navigate={}'.format(
            self.prods_per_page * (self.current_page - 1),
            self.current_page)
        return urlparse.urlunsplit((scheme, netloc, path, query_string, fragment))
