from __future__ import division, absolute_import, unicode_literals

from scrapy.log import INFO, WARNING
from product_ranking.items import SiteProductItem
from .bedbathandbeyond import BedBathAndBeyondProductsSpider
from scrapy.http import Request


class BedBathAndBeyondShelfPagesSpider(BedBathAndBeyondProductsSpider):
    name = 'bedbathandbeyond_shelf_urls_products'
    allowed_domains = ["www.bedbathandbeyond.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(BedBathAndBeyondShelfPagesSpider, self).__init__(*args, **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}.copy()

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta=self._setup_meta_compatibility())

    def _scrape_total_matches(self, response):
        total_matches = response.xpath(
            "//li[contains(@class, 'listCount')]"
            "//span/text()").re('\d+')

        if not total_matches:
            total_matches = response.xpath("//span[@id='allCount']/text()").re('\d+')

        if total_matches:
            return int(total_matches[0])
        else:
            self.log('Can not find Total matches', WARNING)

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//div[contains(@class, 'prodGridRow')]"
            "//a[contains(@class, 'prodImg')]/@href").extract()
        if links:
            for item_url in links:
                yield item_url, SiteProductItem()
        else:
            self.log("Found no product links in {url}".format(
                url=response.url), WARNING)

    def _scrape_next_results_page_link(self, response):
        if self.current_page < self.num_pages:
            self.current_page += 1

            url = response.xpath(
                "//*[@class='listPageNumbers']/ul/li[@class='active']/following-sibling::li[1]/a/@href").extract()

            if url:
                return url[0]
            else:
                self.log("Found no 'next page' links")
                return None
        else:
            return None
