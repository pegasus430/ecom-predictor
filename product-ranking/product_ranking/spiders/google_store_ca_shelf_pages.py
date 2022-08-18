from scrapy.http import Request

from product_ranking.items import SiteProductItem
from product_ranking.spiders.google_store_ca import GoogleStoreCaProductsSpider


class GoogleStoreCaShelfPagesSpider(GoogleStoreCaProductsSpider):
    name = 'google_store_ca_shelf_urls_products'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(GoogleStoreCaShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(
            url=self.product_url,
            meta={
                'remaining': self.quantity,
                'search_term': ''
            }
        )

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//a[contains(@class,"mqn-aah")]/@href'
        ).extract()
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if self.current_page < self.num_pages:
            self.current_page += 1

            return super(GoogleStoreCaShelfPagesSpider, self)._scrape_next_results_page_link(response)

    def _get_products(self, response):
        for request in super(GoogleStoreCaShelfPagesSpider, self)._get_products(response):
            yield request.replace(dont_filter=True)