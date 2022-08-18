from __future__ import absolute_import, division, unicode_literals

from scrapy.http import Request

from .coopnl import CoopnlProductsSpider


class CoopnlShelfPagesSpider(CoopnlProductsSpider):
    name = 'coopnl_shelf_urls_products'
    allowed_domains = ["www.coop.nl"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(CoopnlProductsSpider, self).__init__(
            *args,
            **kwargs)

        self.product_url = self.product_url.replace('\'', '')
        self.current_page = 0

    def start_requests(self):
        yield Request(
            url=self.product_url,
            meta={'remaining': self.quantity, 'search_term': ''},
            dont_filter=True
        )

    def _scrape_next_results_page_link(self, response):
        meta = response.meta

        if not meta.get('total_count'):
            total_count = self._scrape_total_matches(response)
            meta['total_count'] = total_count
        if not meta.get('category_name'):
            category_name = response.xpath("//input[@name='CategoryName']/@value").extract()
            if category_name:
                meta['category_name'] = category_name[0]

        total_count = meta.get('total_count')
        if total_count and self.current_page * 12 > total_count:
            return
        category_name = meta.get('category_name')
        self.current_page += 1

        if category_name:
            next_link = self.CATEGORY_NEXT_PAGE_URL.format(page_num=self.current_page, category_name=category_name)

        return Request(
            next_link,
            meta=meta
        )

