from __future__ import division, absolute_import, unicode_literals

from scrapy import Request

from product_ranking.items import SiteProductItem
from product_ranking.spiders.costco import CostcoProductsSpider


class CostcoShelfUrlsSpider(CostcoProductsSpider):
    name = "costco_shelf_urls_products"

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(CostcoShelfUrlsSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(self.product_url, meta={'remaining':self.quantity, "search_term":''})

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//div[contains(@class,"product-list")]//p[@class="description"]/a/@href'
        ).extract()
        if not links:
            links = response.xpath('.//a[@class="thumbnail" and @itemid]/@href').extract()
        shelf_categories = [c.strip() for c in response.xpath('.//*[@class="crumbs"]/li//text()').extract()
                            if len(c.strip()) > 1 and not "Home" in c]
        shelf_category = shelf_categories[-1] if shelf_categories else None
        for item_url in links:
            item = SiteProductItem()
            if shelf_category:
                item['shelf_name'] = shelf_category
            if shelf_categories:
                item['shelf_path'] = shelf_categories
            yield item_url, item

    def _scrape_results_per_page(self, response):
        count = response.css(".table-cell.results.hidden-xs.hidden-sm.hidden-md>span").re(
            r"Showing\s\d+-(\d+)\s?of")
        count = int(count[0].replace('.', '').replace(',', '')) if count else None
        return count

    def _scrape_next_results_page_link(self, response):
        if self.current_page > self.num_pages:
            return

        self.current_page += 1
        links = response.xpath('//div[contains(@class, "paging")]//li[@class="forward"]/a/@href').extract()
        if links:
            link = links[0]
            return link

