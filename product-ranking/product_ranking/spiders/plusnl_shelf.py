# -*- coding: utf-8 -*-

from .plusnl import PlusnlProductsSpider
from scrapy.http import Request
import urlparse


class PlusnlShelfPagesSpider(PlusnlProductsSpider):
    name = 'plusnl_shelf_urls_products'
    allowed_domains = ["www.plus.nl"]

    SHELF_NEXT_PARAM = "PageNumber={page_num}&PageSize=12&SortingAttribute=&CategoryName={category_num}" \
                       "&SearchParameter=%26%40QueryTerm%3D*%26ContextCategoryUUID%26OnlineFlag%3D1" \
                       "&CatalogID=WEB"

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(PlusnlShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "",
                            'remaining': self.quantity,
                            'prod_count': 12},
                      )

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        next_link = None
        cat_num = response.xpath("//*[contains(@name, 'SortingAttribute')]"
                                 "/@data-document-location").re(r'(?<=CategoryName=)(\d+)')
        total_count = self._scrape_total_matches(response)

        prod_count = meta.get('prod_count')

        self.current_page += 1

        if total_count and total_count < self.current_page * prod_count:
            return

        if cat_num:
            scheme, netloc, url, params, query, fragment = urlparse.urlparse(response.url)
            query = self.SHELF_NEXT_PARAM.format(
                page_num=self.current_page, category_num=cat_num[0])
            next_link = urlparse.urlunparse((scheme, netloc, url, params, query, fragment))

        return Request(
            next_link,
            meta=meta
        )
