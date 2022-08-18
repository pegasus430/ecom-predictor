from __future__ import absolute_import, division, unicode_literals

from scrapy.http import Request

from product_ranking.items import SiteProductItem
from product_ranking.spiders.bestbuy import BestBuyProductSpider


class BestBuyShelfPagesSpider(BestBuyProductSpider):
    name = 'bestbuy_shelf_urls_products'
    allowed_domains = ["bestbuy.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        super(BestBuyShelfPagesSpider, self).__init__(*args, **kwargs)
        self.current_page = 1
        if "num_pages" in kwargs:
            self.num_pages = int(kwargs['num_pages'])
        else:
            self.num_pages = 1

    def start_requests(self):
        if self.product_url:
            yield Request(self.product_url,
                          meta={'search_term': '', 'remaining': self.quantity},
                          headers=self.HEADERS)

    def _scrape_product_links(self, response):
        item_urls = response.xpath(
            './/*[@class="list-item-postcard"]//a[@data-rank="pdp"]/@href').extract()
        shelf_categories = [c.strip() for c in response.xpath('.//*[@class="breadcrumb"]//li//a/text()').extract()
                            if len(c.strip()) > 1 and not c.strip() == "Best Buy"]
        shelf_category = shelf_categories[-1] if shelf_categories else None
        for item_url in item_urls:
            item = SiteProductItem()
            if shelf_category:
                item['shelf_name'] = shelf_category
            if shelf_categories:
                item['shelf_path'] = shelf_categories
            yield item_url, item

    def _scrape_total_matches(self, response):
        matches = response.xpath(
            '//script[contains(text(), "searchResultsNum")]/text()'
        ).re('track\.searchResultsNum\s*=\s*"(\d+)"')
        if matches:
            return int(matches[0])

    def _scrape_next_results_page_link(self, response):
        next_link = response.xpath('.//*[@class="pager-next"]/a/@href').extract()
        next_link = next_link[0] if next_link else None
        if not next_link or self.current_page >= int(self.num_pages):
            return None
        else:
            self.current_page += 1
            return next_link
