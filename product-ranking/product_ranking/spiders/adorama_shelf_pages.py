import re
import urlparse
from product_ranking.items import SiteProductItem
from .adorama import AdoramaProductsSpider
from scrapy import Request
from scrapy.log import DEBUG


class AdoramaShelfPagesSpider(AdoramaProductsSpider):
    name = 'adorama_shelf_urls_products'
    allowed_domains = ["adorama.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(AdoramaShelfPagesSpider, self).__init__(*args, **kwargs)

    def _setup_meta_compatibility(self):
        return {'remaining': self.quantity, 'search_term': ''}

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'remaining': self.quantity,
                            'search_term': ''})

    def _scrape_product_links(self, response):

        product_links = response.xpath('//div[@class="item"]//a[@class="tappable-item"]/@href').extract()

        for link in product_links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return None

        next_page = response.xpath('//div[@class="pagination"]//a[@class="page-next page-control"]/@href').extract()
        self.current_page += 1
        return next_page[0] if next_page else None

    def parse_product(self, response):
        return super(AdoramaShelfPagesSpider, self).parse_product(response)
