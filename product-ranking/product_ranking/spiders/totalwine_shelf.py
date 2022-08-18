# -*- coding: utf-8 -*-

from .totalwine import TotalwineProductsSpider
from scrapy.http import Request
from product_ranking.items import SiteProductItem


class TotalwineShelfPagesSpider(TotalwineProductsSpider):
    name = 'totalwine_shelf_urls_products'
    allowed_domains = ["www.totalwine.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(TotalwineShelfPagesSpider, self).__init__(*args, **kwargs)
        self.NEXT_PAGE_LINK = self.product_url + '?page={page_num}'

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      )

    def _scrape_total_matches(self, response):
        total_match = response.xpath("//input[@id='listCount']/@value").extract()

        return int(total_match[0]) if total_match else 0

    def _scrape_product_links(self, response):
        product_links = response.xpath("//h2[@class='plp-product-title']//a/@href").extract()

        for item_url in product_links:
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return None
        product_links = response.xpath("//h2[@class='plp-product-title']//a/@href").extract()
        if not product_links:
            return

        self.current_page += 1
        next_link = self.NEXT_PAGE_LINK.format(page_num=self.current_page)
        return next_link
