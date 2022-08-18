from scrapy import Request
from .rakuten import RakutenProductsSpider


class RakutenShelfPagesSpider(RakutenProductsSpider):
    name = 'rakuten_shelf_urls_products'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(RakutenShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        meta = {'search_term': "", 'remaining': self.quantity}
        yield Request(
            url=self.product_url,
            meta=meta,
            headers=self.HEADERS
        )

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return None
        self.current_page += 1
        return super(RakutenShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)
