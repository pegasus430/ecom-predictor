import re

from scrapy.http import Request

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.utils import SharedCookies

from .peapod import PeapodProductsSpider


class PeapodShelfPagesSpider(PeapodProductsSpider):
    name = 'peapod_shelf_urls_products'

    SHELF_URL = "https://www.peapod.com/api/{api_version}/user/products?" \
                "catTreeId={category_id}&facet=categories,brands,nutrition,specials,newArrivals,privateLabel&facetExcludeFilter=true" \
                "&filter=&flags=true{category_keyword}&nutrition=true&rows=120&sort=itemsPurchased+desc,+name+asc&start=0&substitute=true"

    handle_httpstatus_list = [403]

    def __init__(self, disable_shared_cookies=False, zip_code=PeapodProductsSpider.DEFAULT_ZIP, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)
        kwargs.pop('quantity', None)
        self.zip_code = zip_code
        super(PeapodProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)
        self.shared_cookies = SharedCookies('peapod') if not disable_shared_cookies else None

    def after_zipcode(self, response):
        if self.shared_cookies:
            self.shared_cookies.unlock()

        if self._retry_recaptcha(response):
            yield self.solve_recaptcha(response)
        elif self.product_url:
            category_keyword = self._extract_category_keyword(self.product_url)
            if category_keyword:
                category_keyword = "&keywords={}".format(category_keyword)
            else:
                category_keyword = ''

            self.product_url = self.SHELF_URL.format(
                category_id=self._extract_category_id(self.product_url),
                category_keyword=category_keyword,
                api_version=self.API_VERSION
            )
            yield Request(self.product_url,
                          meta={'remaining': self.quantity,
                                'search_term': ''}
                          )

    @staticmethod
    def _extract_category_id(url):
        product_id = re.findall(r'categor(?:ies|y)/(\d+)', url)
        return product_id[-1] if product_id else None

    @staticmethod
    def _extract_category_keyword(url):
        product_id = re.findall(r'select/(\w+)', url)
        return product_id[-1] if product_id else ''

    def _scrape_next_results_page_link(self, response):
        # by default shelf scraper return 120 products, no more is needed
        return
