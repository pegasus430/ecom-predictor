from __future__ import division, absolute_import, unicode_literals

import re
import urlparse
from .amazoncn import AmazonProductsSpider
from scrapy.http import Request
from product_ranking.items import SiteProductItem


class AmazonCnShelfPagesSpider(AmazonProductsSpider):
    name = 'amazoncn_shelf_urls_products'
    allowed_domains = ["www.amazon.cn", "amazon.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', 1))
        self.num_pages = min(10, self.num_pages)
        super(AmazonCnShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta=self._setup_meta_compatibility())

    def _scrape_total_matches(self, response):
        totals = response.xpath('//*[contains(@id, "s-result-count")]/text()').extract()
        if totals:
            totals = re.findall('\d+', totals[0].replace(',', ''))
            return int(totals[-1]) if totals else 0

    def _scrape_product_links(self, response):
        product_links = response.xpath("//a[contains(@class, 's-access-detail-page')]/@href").extract()
        for product_link in product_links:
            item = SiteProductItem()
            yield product_link, item

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return None
        next_link = response.xpath("//a[@id='pagnNextLink']/@href").extract()
        current_page += 1
        response.meta['current_page'] = current_page
        if next_link:
            url = urlparse.urljoin(response.url, next_link[0])
            return Request(url=url, meta=response.meta)
