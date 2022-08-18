from __future__ import division, absolute_import, unicode_literals

from .grocerygateway import GroceryGatewayProductsSpider
from scrapy.http import Request


class GroceryGatewayShelfPagesSpider(GroceryGatewayProductsSpider):
    name = 'grocerygateway_shelf_urls_products'
    allowed_domains = ["grocerygateway.com"]

    CATEGORY_FULL_URL = 'https://www.grocerygateway.com/store/groceryGateway/en' \
                        '{category_url}?page={page_num}&q=&current={offset}&sort=relevance'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        self.CATEGORY_URL = None

        super(GroceryGatewayShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta=self._setup_meta_compatibility())

    def _scrape_total_matches(self, response):
        totals = response.xpath('//span[@class="nb-result"]/text()').re('\d+')
        return int(totals[0]) if totals else 0

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        current_page = meta.get('current_page', 1)
        total_matches = meta.get('total_matches', 0)
        if current_page >= self.num_pages or 24 * current_page >= total_matches:
            return
        current_page += 1
        if not self.CATEGORY_URL:
            category_url = response.xpath('//div[@id="showMore"]/@data-loadmoreactionurl').extract()
            self.CATEGORY_URL = category_url[0] if category_url else None

        url = self.CATEGORY_FULL_URL.format(
            category_url=self.CATEGORY_URL,
            page_num=current_page-1,
            offset=(current_page-1)*24
        ) if self.CATEGORY_URL else None
        meta['current_page'] = current_page
        return Request(
            url=url,
            meta=meta
        ) if url else None