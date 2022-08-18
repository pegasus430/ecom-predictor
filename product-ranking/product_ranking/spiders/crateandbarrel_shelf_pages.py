from scrapy import Request
from scrapy.log import INFO
import urlparse

from product_ranking.items import SiteProductItem
from .crateandbarrel import CrateandbarrelProductsSpider
from product_ranking.utils import valid_url


class CrateandbarrelShelfPagesSpider(CrateandbarrelProductsSpider):
    name = "crateandbarrel_shelf_urls_products"

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))
        super(CrateandbarrelShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      meta={'search_term': '', 'remaining': self.quantity})

    @staticmethod
    def _scrape_total_matches(response):
        total_matches = response.xpath('//a[contains(@class, "product-miniset-thumbnail")]'
                                       '/@href').extract()
        return len(total_matches) if total_matches else None

    def _scrape_product_links(self, response):
        items = response.xpath('//a[contains(@class, "product-miniset-thumbnail")]'
                               '/@href').extract()

        if items:
            for item in items:
                res_item = SiteProductItem()
                link = urlparse.urljoin(response.url, item)
                yield link, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        # There is no pages, all products are on the first page
        return