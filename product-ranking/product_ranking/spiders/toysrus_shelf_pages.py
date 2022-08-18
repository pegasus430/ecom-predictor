import math

from scrapy.http import Request

from product_ranking.items import SiteProductItem
from product_ranking.utils import valid_url

from .toysrus import ToysrusProductsSpider


class ToysrusShelfPagesSpider(ToysrusProductsSpider):
    name = 'toysrus_shelf_urls_products'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(ToysrusShelfPagesSpider, self).__init__(
            *args, **kwargs)

    def start_requests(self):
        if self.product_url and 'index.jsp' in self.product_url:
            self.product_url = self.product_url.replace('/index.jsp', '').replace('http', 'https').lower()
        yield Request(url=valid_url(self.product_url),
                      meta={'search_term': '', 'remaining': self.quantity},
                      dont_filter=True,
                      cookies={'route': 't2'})


    def _scrape_next_results_page_link(self, response):
        if self.current_page < self.num_pages:
            total_matches = self._scrape_total_matches(response)
            results_per_page = self._scrape_results_per_page(response)
            if not results_per_page:
                results_per_page = 24
            if (total_matches and results_per_page
                and self.current_page < math.ceil(total_matches / results_per_page)):
                self.current_page += 1
                offset = '&page={}'.format(self.current_page)
                url = self.product_url + offset
                return url

    def _scrape_product_links(self, response):
        product_links = list(super(ToysrusShelfPagesSpider, self)._scrape_product_links(response))
        if len(product_links):
            for product_link in product_links:
                yield product_link
        else:
            product_links = response.xpath('//div/a[@class="bnsProductBlock"][1]/@href').extract()
            for product_link in product_links:
                yield product_link, SiteProductItem()
