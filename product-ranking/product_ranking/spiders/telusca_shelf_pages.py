from scrapy.http import Request

from product_ranking.items import SiteProductItem
from .telusca import TelusCAProductsSpider


class TelusCAShelfPagesSpider(TelusCAProductsSpider):
    name = 'telusca_shelf_urls_products'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(TelusCAShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def start_requests(self):
        return super(TelusCAShelfPagesSpider, self).start_requests()

    def _start_requests(self, response):
        yield Request(url=self.product_url,
                      meta=self._setup_meta_compatibility())

    def _setup_meta_compatibility(self):
        return {'remaining': self.quantity, 'search_term': ''}

    def _scrape_product_links(self, response):
        items = response.xpath("//ul[@class='grid-row category-group__list']//"
                               "li//a[@class='category-product__image']/@href").extract()

        for item in items:
            yield item, SiteProductItem()

    def _scrape_total_matches(self, response):
        return None

    def _scrape_next_results_page_link(self, response):
        pass
