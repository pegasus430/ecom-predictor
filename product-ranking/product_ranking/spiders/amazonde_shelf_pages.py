from __future__ import division, absolute_import, unicode_literals

from .amazonde import AmazonProductsSpider
from scrapy.http import Request
from product_ranking.items import SiteProductItem

class AmazonDeShelfPagesSpider(AmazonProductsSpider):
    name = 'amazonde_shelf_urls_products'
    allowed_domains = ["www.amazon.de", "amazon.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))
        self.num_pages = min(10, self.num_pages)
        super(AmazonDeShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta=self._setup_meta_compatibility())

    def _scrape_product_links(self, response):
        product_links = response.xpath("//a[contains(@class, 'a-link-normal s-access-detail-page')]/@href").extract()
        for product_link in product_links:
            item = SiteProductItem()
            yield product_link, item

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return None
        next = response.xpath("//a[@id='pagnNextLink']/@href").extract()
        self.current_page += 1
        if next:
            return next[0]