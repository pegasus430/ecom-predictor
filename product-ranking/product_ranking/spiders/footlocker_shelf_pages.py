import re
import urlparse
from product_ranking.items import SiteProductItem
from .footlocker import FootlockerProductsSpider
from scrapy import Request
from scrapy.log import DEBUG


class FootlockerShelfPagesSpider(FootlockerProductsSpider):
    name = 'footlocker_shelf_urls_products'
    allowed_domains = ["www.footlocker.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(FootlockerShelfPagesSpider, self).__init__(*args, **kwargs)

    def _setup_meta_compatibility(self):
        return {'remaining': self.quantity, 'search_term': ''}

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'remaining': self.quantity,
                            'search_term': ''})

    def _scrape_product_links(self, response):
        self.product_links = response.xpath(
            '//div[@id="endeca_search_results"]//ul//li//a[@class="quickviewEnabled"]/@href').extract()

        for link in self.product_links:
            yield link, SiteProductItem()


    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return None

        next_link = response.xpath('//a[@class="next"]/@href').extract()
        self.current_page += 1
        return next_link[0] if next_link else None

    def parse_product(self, response):
        return super(FootlockerShelfPagesSpider, self).parse_product(response)
