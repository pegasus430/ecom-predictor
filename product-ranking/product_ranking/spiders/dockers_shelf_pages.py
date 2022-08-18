# -*- coding: utf-8 -*-

from .dockers import DockersProductsSpider
from scrapy.http import Request
from urlparse import urljoin


class DockersShelfPagesSpider(DockersProductsSpider):
    name = 'dockers_shelf_urls_products'
    allowed_domains = ["www.dockers.com"]

    PAGINATE_URL = 'http://www.dockers.com/US/en_US/includes/searchResultsScroll/?nao={nao}&url={url}'

    PAGINATE_BY = 120
    handle_httpstatus_list = [404]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(DockersShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      )

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return
        current_page += 1
        response.meta.update({
            'current_page': current_page
        })
        url = super(DockersShelfPagesSpider, self)._scrape_next_results_page_link(response)
        if url:
            return Request(
                url=urljoin(response.url, url),
                meta=response.meta
            )
