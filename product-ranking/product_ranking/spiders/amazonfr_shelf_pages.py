from __future__ import division, absolute_import, unicode_literals

from .amazonfr import AmazonProductsSpider
from scrapy.http import Request
from product_ranking.items import SiteProductItem


class AmazonFrShelfPagesSpider(AmazonProductsSpider):
    name = 'amazonfr_shelf_urls_products'
    allowed_domains = ["www.amazon.fr", "amazon.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))
        self.num_pages = min(10, self.num_pages)
        super(AmazonFrShelfPagesSpider, self).__init__(
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
            if '/gp/' not in product_link:
                item = SiteProductItem()
                yield product_link, item

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return None
        next_link = response.xpath("//a[@id='pagnNextLink']/@href").extract()
        self.current_page += 1
        if next_link:
            return next_link[0]
