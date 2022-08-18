from scrapy.http import Request
from product_ranking.items import SiteProductItem
import urlparse
from scrapy.log import INFO
from product_ranking.utils import valid_url
from .potterybarn import PotterybarnProductsSpider


class PotterybarnShelfPagesSpider(PotterybarnProductsSpider):
    name = 'potterybarn_shelf_urls_products'
    allowed_domains = ["www.potterybarn.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))

        super(PotterybarnProductsSpider, self).__init__(
            *args,
            **kwargs)

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      meta={'search_term': '', 'remaining': self.quantity})

    def _scrape_product_links(self, response):
        items = response.xpath('//ul[contains(@class, "product-list")]'
                               '/li/div[contains(@class, "product-thumb")]'
                               '//a/@href').extract()

        if items:
            for item in items:
                res_item = SiteProductItem()
                yield item, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        if self.current_page < self.num_pages:
            self.current_page += 1

            next_page = response.xpath('.//a[@id="nextPage"]/@href').extract()

            if next_page:
                return urlparse.urljoin(response.url, next_page[0])

    def _scrape_total_matches(self, response):
        return None
