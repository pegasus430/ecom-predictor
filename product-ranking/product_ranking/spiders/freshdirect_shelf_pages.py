import re
from .freshdirect import FreshDirectProductsSpider
from scrapy import Request


class FreshdirectShelfPagesSpider(FreshDirectProductsSpider):
    name = 'freshdirect_shelf_urls_products'
    allowed_domains = ["www.freshdirect.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.product_url = kwargs['product_url']
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(FreshdirectShelfPagesSpider, self).__init__(*args, **kwargs)
        self.product_url = self.product_url.replace('activePage=1', 'activePage={}')

    @staticmethod
    def valid_url(url):
        if not re.findall(r"http(s){0,1}\:\/\/", url):
            url = "http://" + url
        return url

    def start_requests(self):
        product_url = self.product_url.format(self.current_page)
        yield Request(url=self.valid_url(product_url),
                      meta={'remaining': self.quantity,
                            'search_term': ''})

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        if self.current_page * self.results_per_page >= self._scrape_total_matches(response):
            return
        self.current_page += 1
        next_link = self.product_url.format(self.current_page)
        if next_link:
            return next_link

    def parse_product(self, response):
        return super(FreshdirectShelfPagesSpider, self).parse_product(response)