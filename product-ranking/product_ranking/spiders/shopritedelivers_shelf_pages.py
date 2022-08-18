import urlparse
from scrapy import Request
from .shopritedelivers import ShopritedeliversProductsSpider
from product_ranking.items import SiteProductItem


class ShopritedeliversShelfPagesSpider(ShopritedeliversProductsSpider):
    name = "shopritedelivers_shelf_urls_products"

    def __init__(self, *args, **kwargs):
        super(ShopritedeliversShelfPagesSpider, self).__init__(*args, **kwargs)

        self.current_page = 1
        if "num_pages" in kwargs:
            self.num_pages = int(kwargs['num_pages'])
        else:
            self.num_pages = 1

    @staticmethod
    def _parse_shelf_name(response):
        shelf_name = response.xpath('//div[@class="pageHeader"]/h1/text()').extract()
        return shelf_name[0] if shelf_name else None

    def _parse_shelf_path(self, response):
        return self._parse_categories(response)

    def start_requests(self):
        if self.product_url:
            yield Request(self.product_url,
                          meta={'search_term': '', 'remaining': self.quantity},)

    def _scrape_product_links(self, response):
        product_links_raw = response.xpath(
            '//*[@class="itemContainer"]//a[contains(@id, "_ProductName")]/@href'
        ).extract()
        urljoin = lambda x: urlparse.urljoin(response.url, x)
        links = [urljoin(link) for link in product_links_raw]
        shelf_name = self._parse_shelf_name(response)
        shelf_path = self._parse_shelf_path(response)
        shelf_path.append(shelf_name)
        for item_url in links:
            item = SiteProductItem()
            item['shelf_name'] = shelf_name
            item['shelf_path'] = shelf_path
            yield item_url, item

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        return super(ShopritedeliversShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)
