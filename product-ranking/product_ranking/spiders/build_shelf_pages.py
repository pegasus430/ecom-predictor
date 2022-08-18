from scrapy import Request

from .build import BuildProductsSpider


class BuildShelfProductsSpider(BuildProductsSpider):
    name = 'build_shelf_urls_products'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(BuildShelfProductsSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(
            self.product_url,
            meta={'remaining': self.quantity, 'search_term': ''}
        )

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page', 1)
        if current_page < self.num_pages:
            return super(BuildShelfProductsSpider, self)._scrape_next_results_page_link(response)
