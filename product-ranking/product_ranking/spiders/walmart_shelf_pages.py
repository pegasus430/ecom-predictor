from scrapy.http import Request

from product_ranking.utils import replace_http_with_https, valid_url

from .walmart import WalmartProductsSpider


class WalmartShelfPagesSpider(WalmartProductsSpider):
    name = 'walmart_shelf_urls_products'
    allowed_domains = ["walmart.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(WalmartShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        zip_code = getattr(self, 'zip_code', None)
        store = getattr(self, 'store', None)
        if zip_code and not store:
            yield Request(
                url=self.STORE_SEARCH_URL.format(zip_code=zip_code),
                callback=self.find_store_for_zip_code
            )
        else:
            self.cookies = {'PSID': store if store else self.DEFAULT_STORE}
            self.product_url = replace_http_with_https(self.product_url)

            yield Request(url=valid_url(self.product_url),
                          meta={'remaining': self.quantity, 'search_term': ''},
                          cookies=self.cookies
                          )

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        return super(WalmartShelfPagesSpider, self)._scrape_next_results_page_link(response)
