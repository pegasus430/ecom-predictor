import re
import urlparse

from scrapy.http import Request

from product_ranking.items import SiteProductItem
from .petco import PetcoProductsSpider

is_empty = lambda x: x[0] if x else None


class PetcoShelfPagesSpider(PetcoProductsSpider):
    name = 'petco_shelf_urls_products'
    allowed_domains = ['petco.com', 'www.petco.com']

    def _setup_class_compatibility(self):
        """ Needed to maintain compatibility with the SC spiders baseclass """
        self.quantity = 99999
        self.site_name = self.allowed_domains[0]
        self.user_agent_key = None
        self.zip_code = '12345'
        self.current_page = 1

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': 99999, 'search_term': ''}.copy()

    def __init__(self, *args, **kwargs):
        super(PetcoShelfPagesSpider, self).__init__(*args, **kwargs)
        self._setup_class_compatibility()
        self.product_url = kwargs['product_url']
        if "num_pages" in kwargs:
            self.num_pages = int(kwargs['num_pages'])
        else:
            self.num_pages = 1
        self.user_agent = "Mozilla/5.0 (X11; Linux i686 (x86_64))" \
                          " AppleWebKit/537.36 (KHTML, like Gecko)" \
                          " Chrome/37.0.2062.120 Safari/537.36"

        self.shelf_next_param = "%23facet:&productBeginIndex:{}&orderBy:&pageView:&minPrice:&maxPrice:&pageSize:24&"

        # variants are switched off by default, see Bugzilla 3982#c11
        self.scrape_variants_with_extra_requests = False
        if 'scrape_variants_with_extra_requests' in kwargs:
            scrape_variants_with_extra_requests = kwargs['scrape_variants_with_extra_requests']
            if scrape_variants_with_extra_requests in (1, '1', 'true', 'True', True):
                self.scrape_variants_with_extra_requests = True

    @staticmethod
    def valid_url(url):
        if not re.findall("http(s){0,1}\:\/\/", url):
            url = "http://" + url
        return url

    def start_requests(self):
        yield Request(url=self.valid_url(self.product_url),
                      meta=self._setup_meta_compatibility())

    def _scrape_product_links(self, response):
        urls = response.xpath(
            "//div[contains(@class,'product-display-grid')]"
            "//div[contains(@class,'product-image')]/a/@href"
            ).extract()
        urls = [urlparse.urljoin(response.url, x) if x.startswith('/') else x
                for x in urls]

        categories = response.css('.breadcrumb a::text').extract()
        shelf_categories = categories if categories else None

        shelf_category = categories[-1] if categories else None

        urls = ["".join(i.replace('http://www.petco.com', '')) for i in urls]

        for url in urls:
            item = SiteProductItem()
            if shelf_categories:
                item['shelf_name'] = shelf_categories
            if shelf_category:
                item['shelf_path'] = shelf_category
            req = Request(
                url,
                callback=self.parse_product,
                meta={
                    'product': item,
                    'search_term': '',
                    'remaining': self.quantity
                },
                dont_filter=True
            )
            yield req, item

    def _scrape_total_matches(self, response):
        total = re.findall('totalSearchCount:(\d+),', response.body)
        return int(total[0]) if total else 0

    def _scrape_next_results_page_link(self, response):
        scraped_page = response.meta.get('scraped_results_per_page')
        begin_index = self.current_page * scraped_page

        if begin_index >= self._scrape_total_matches(response):
            return
        if self.current_page >= self.num_pages:
            return

        self.current_page += 1

        next_page_param = self.shelf_next_param.format(begin_index)
        next_link = self.product_url + next_page_param
        if next_link:
            return next_link