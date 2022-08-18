# -*- coding: utf-8 -*-

from .ebay import EbayProductsSpider
from scrapy.http import Request


class EbayShelfPagesSpider(EbayProductsSpider):
    name = 'ebay_shelf_urls_products'
    allowed_domains = ["ebay.com"]
    HOME_URL = 'https://www.ebay.com'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(EbayShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      )

    def _scrape_total_matches(self, response):
        total_matches = super(EbayShelfPagesSpider, self)._scrape_total_matches(response)
        if not total_matches:
            total_matches = response.xpath('//h2[@class="srp-controls__count-heading"]/text()').re('\d{1,3}[,\.\d]*')
            total_matches = int(total_matches[-1].replace(',', '')) if total_matches else None
        return total_matches

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return
        current_page += 1
        response.meta['current_page'] = current_page
        request = super(EbayShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)
        if request:
            return request

        next_url = response.xpath('//div[@class="b-pagination"]//a[@rel="next"]/@href').extract()
        if next_url:
            return Request(
                next_url[0],
                meta=response.meta
            )
