from __future__ import division, absolute_import, unicode_literals

from product_ranking.spiders.safeway import SafeWayProductsSpider
from scrapy.http import Request
from scrapy.log import ERROR


class SafeWayShelfPagesSpider(SafeWayProductsSpider):
    name = 'safeway_shelf_urls_products'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(SafeWayShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _start_requests(self, response):
        yield Request(
            url=self.product_url,
            meta={'remaining': self.quantity, 'search_term': ''},
            headers=self.headers,
            callback=self._extract_data
        )

    def _extract_data(self, response):
        data = response.xpath('//input[@name="gridDataSource"]/@value').extract()
        if data:
            response = response.replace(body=data[0].replace('&#34;', '"'))
            return self.parse(response)
        self.log("Unable to get shelf info", ERROR)
