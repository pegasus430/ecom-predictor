import re
import urlparse
from product_ranking.items import SiteProductItem
from .drugstore import DrugstoreProductsSpider
from scrapy import Request


class DrugstoreShelfPagesSpider(DrugstoreProductsSpider):
    name = 'drugstore_shelf_urls_products'
    allowed_domains = ["drugstore.com",
                       "recs.richrelevance.com"]

    def __init__(self, *args, **kwargs):
        super(DrugstoreShelfPagesSpider, self).__init__(*args, **kwargs)
        self.product_url = kwargs['product_url']

        if "num_pages" in kwargs:
            self.num_pages = int(kwargs['num_pages'])
        else:
            self.num_pages = 1

        self.prods_per_page = 18

        self.quantity = self.num_pages * self.prods_per_page
        if "quantity" in kwargs:
            self.quantity = int(kwargs['quantity'])
        self.current_page = 1

    @staticmethod
    def valid_url(url):
        if not re.findall(r"http(s){0,1}\:\/\/", url):
            url = "http://" + url
        return url

    def start_requests(self):
        yield Request(url=self.valid_url(self.product_url),
                      meta={'remaining': self.quantity,
                            'search_term': ''})

    def _scrape_product_links(self, response):
        urls = response.xpath('//div[@class="info"]/'
                              'span/a[@class="oesLink"]/'
                              '@href').extract()
        urls = [urlparse.urljoin(response.url, x) if x.startswith('/') else x
                for x in urls]

        # parse shelf category
        shelf_categories = response.xpath('//td[@itemprop="breadcrumb"]/'
                                          'a[@class="srchLink"]/'
                                          'text()').extract()
        shelf_category = response.xpath('//td[@itemprop="breadcrumb"]//'
                                        'h1[@class="breadCrumbH1"]/'
                                        'text()').extract()
        shelf_categories += shelf_category
        for url in urls:
            item = SiteProductItem()
            if shelf_categories:
                item['shelf_name'] = shelf_categories
            if shelf_category:
                item['shelf_path'] = shelf_category
            yield url, item

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        return super(DrugstoreShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)

    def parse_product(self, response):
        return super(DrugstoreShelfPagesSpider, self).parse_product(response)
