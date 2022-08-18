from scrapy import Request

from product_ranking.utils import valid_url

from .overstock import OverstockProductsSpider


class OverstockShelfPagesSpider(OverstockProductsSpider):
    name = 'overstock_shelf_urls_products'
    allowed_domains = ["overstock.com", "www.overstock.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        super(OverstockShelfPagesSpider, self).__init__(*args, **kwargs)

        if "num_pages" in kwargs:
            self.num_pages = int(kwargs['num_pages'])
        else:
            self.num_pages = 1
        self.current_page = 1

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      meta={'remaining': self.quantity,
                            'search_term': ''})

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        return super(OverstockShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)
