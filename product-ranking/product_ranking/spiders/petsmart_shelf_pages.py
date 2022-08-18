from __future__ import division, absolute_import, unicode_literals
from scrapy import Request

from product_ranking.items import SiteProductItem
from product_ranking.spiders.petsmart import PetsmartProductsSpider


class PetsmartShelfUrlsSpider(PetsmartProductsSpider):
    name = "petsmart_shelf_urls_products"
    ROOT_URL = 'www.petsmart.com'

    def __init__(self, *args, **kwargs):
        super(PetsmartShelfUrlsSpider, self).__init__(*args, **kwargs)
        if "num_pages" in kwargs:
            self.num_pages = int(kwargs['num_pages'])
        else:
            self.num_pages = 1
        self.current_page = 1

    def start_requests(self):
        yield Request(self.product_url, meta={'remaining': self.quantity, "search_term": ''})

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//ul[contains(@class,"search-result-items")]/li/a/@href'
        ).extract()
        if not links:
            links = response.xpath('//a[@class="name-link"]/@href').extract()
        if links:
            for i in range(len(links)):
                if self.ROOT_URL not in links[i]:
                    links[i] = 'http://' + self.ROOT_URL + links[i]

        cats = response.xpath('.//link[@rel="canonical"]/@href').extract()
        shelf_categories = []
        shelf_category = ''

        if cats:
            shelf_categories = [c.strip() for c in cats[0].split('/') if len(c.strip()) > 1]
            shelf_category = shelf_categories[-1] if shelf_categories else None
        for item_url in links:
            item = SiteProductItem()
            if shelf_category:
                item['shelf_name'] = shelf_category
            if shelf_categories:
                item['shelf_path'] = shelf_categories
            yield item_url, item

    def _scrape_results_per_page(self, response):
        count = response.xpath('//ul[@class="items-per-page-options"]/li[@class="selected"]/text()').extract()
        count = int(count[0]) if count else None
        return count

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= int(self.num_pages):
            return None

        self.current_page += 1
        links = response.xpath(
            './/li[@class="current-page"]/following-sibling::li[1]/a/@href'
        ).extract()

        if links:
            return links[0]
