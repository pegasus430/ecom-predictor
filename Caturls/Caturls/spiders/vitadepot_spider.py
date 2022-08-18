__author__ = 'Lai Tash (lai.tash@yandex.ru)'

from scrapy import Request

from Caturls.spiders.caturls_spider import CaturlsSpider
from Caturls.items import ProductItem


class VitadepotSpider(CaturlsSpider):
    name = "vitadepot"

    allowed_domains = ["vitadepot.com"]

    def parse(self, response):
        boxes = self._scrape_product_boxes(response)
        if boxes is None:  # No products are shown here, go deeper into subcategories.
            for request in map(Request, self._scrape_subcategories(response)):
                yield request
        else:
            # Scrape product links.
            category_name = self._scrape_category_name(response)
            for url in map(self._scrape_product_link, boxes):
                yield ProductItem(product_url=url, category=category_name)

            # Go to next page, if availible.
            url = response.css('a.next.i-next::attr(href)')
            if url:
                yield Request(url.extract()[0])

    @staticmethod
    def _scrape_product_boxes(response):
        if len(response.css(':not(#cat_bestSellers) > .category-products')) == 0:
            return None
        return response.css(':not(#cat_bestSellers) > .category-products .item')

    @staticmethod
    def _scrape_product_link(box):
        return box.css('.product-name a::attr(href)').extract()[0]

    @staticmethod
    def _scrape_category_name(response):
        return (response.css('.category-title h1::text').extract() or [None])[0]

    @staticmethod
    def _scrape_subcategories(response):
        names = response.css('dl#narrow-by-list dt::text').extract()
        fields = response.css('dl#narrow-by-list dd')
        return (li.css('a::attr(href)').extract()[0] for li in (field for name, field in zip(names, fields)
                                                                if name != "Shop By Category"))