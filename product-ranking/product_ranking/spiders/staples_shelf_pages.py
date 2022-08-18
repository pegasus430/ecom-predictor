import re

from scrapy.http import Request

from .staples import StaplesProductsSpider


class StaplesShelfPagesSpider(StaplesProductsSpider):
    name = 'staples_shelf_urls_products'
    allowed_domains = ['www.staples.com', 'static.www.turnto.com']


    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(StaplesShelfPagesSpider, self).__init__(*args, **kwargs)
        self.product_url = self.get_shelf_url(self.product_url, 1)

    def start_requests(self):
        yield Request(
            url=self.product_url,
            meta={'search_term': "", 'remaining': self.quantity}
        )

    # Shelf component
    def get_shelf_url(self, url, page):
        def get_directory_name(url):
            return re.search(r'staples\.com\/(.+?)\/cat_', url).group(1)
        def get_category_id(url):
            return re.search(r'staples\.com\/.+?\/cat_([\w\d]+)', url).group(1)
        return self.SHELF_URL.format(
            directory_name=get_directory_name(url),
            category_id=get_category_id(url),
            page=page
        )

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return None
        self.current_page += 1
        if response.xpath('//input[@id="lastPage" and @value="false"]'):
            return self.get_shelf_url(
                self.product_url,
                int(response.xpath('//input[@id="pagenum"]/@value').extract()[0]) + 1
            )

    def _scrape_total_matches(self, response):
        return
