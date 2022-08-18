import re
import urllib
import json
import urlparse
from product_ranking.items import SiteProductItem
from .zulily import ZulilyProductsSpider
from scrapy import Request
from scrapy.log import DEBUG, ERROR, INFO, WARNING


class ZulilyShelfPagesSpider(ZulilyProductsSpider):
    name = 'zulily_shelf_pages_products'
    allowed_domains = ["zulily.com", "www.res-x.com"]
    LOG_IN_URL = "https://www.zulily.com/auth"
    BASE_URL = "http://www.zulily.com/"

    product_filter = []

    def __init__(self, *args, **kwargs):
        super(ZulilyShelfPagesSpider, self).__init__(*args, **kwargs)
        self.product_url = kwargs['product_url']

        self.current_page = 1
        #settings.overrides['USE_PROXIES'] = True

    def start_requests(self):
        #Category
        event_id = re.findall(r"/e/.*-((\d)+)\.html", self.product_url)
        if event_id:
            url = self.BASE_URL + "event/" + event_id[0][0]
            yield Request(
                url,
                meta={'remaining':self.quantity, "search_term":''},
                headers=self._get_antiban_headers()
            )
        else:
            #Search
            parsed = urlparse.urlparse(self.product_url)

            if urlparse.parse_qs(parsed.query)['fromSearch']:
                search_term = urlparse.parse_qs(parsed.query)['searchTerm']
                url = self.BASE_URL + "mainpanel/search_carousel/?q=" + search_term
                yield Request(
                    url,
                    meta={'remaining': self.quantity, "search_term": ''},
                    headers=self._get_antiban_headers()
                )

    @staticmethod
    def _get_antiban_headers():
        return {
            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:32.0) Gecko/20100101 Firefox/32.0',
            'Connection': 'keep-alive',
            'Accept-Language': 'en-US,en;q=0.8',
            'Accept': '*/*',
            'X-Requested-With': 'XMLHttpRequest',
            'Accept-Encoding': 'gzip, deflate, sdch'
        }
    @staticmethod
    def valid_url(url):
        if not re.findall(r"http(s){0,1}\:\/\/", url):
            url = "http://" + url
        return url

    def _scrape_product_links(self, response):
        urls = response.xpath(
            "//ul[contains(@class,'products-grid')]/li//a[contains(@class, 'product-image')]/@href").extract()
        urls = [urlparse.urljoin(response.url, x) if x.startswith('/') else x
                for x in urls]

        if not urls:
            self.log("Found no product links.", DEBUG)

        # parse shelf category
        shelf_categories = response.xpath(
            '//div[@class="card_container"]//div[contains(@class, "no_gutter")]//a/@href').extract()
        shelf_categories = [category.strip() for category in shelf_categories]
        shelf_categories = filter(None, shelf_categories)
        try:
            shelf_name = response.xpath('//meta[@name="og:title"]/@content').extract()[0].strip()
        except IndexError:
            pass
        for url in urls:
            item = SiteProductItem()
            if shelf_categories:
                item['shelf_name'] = shelf_name
                item['shelf_path'] = shelf_categories[1:]
            yield url, item

    def page_nums(self, list):
        num_list = [int(n) for n in list if n.isdigit()]
        if len(num_list) > 0:
            return max(num_list)
        else:
            return 1

    def _scrape_next_results_page_link(self, response):
        num_pages = self.page_nums(response.xpath("//div[@class='pagination_container']/nav/ul/li/a/text()").extract())
        if self.current_page >= num_pages:
            return
        self.current_page += 1

        next_page = response.xpath("//div[@class='pagination_container']/nav/ul/li/a[@class='next_page_on']").extract()
        if next_page:
            return urlparse.urljoin(response.url, next_page[0])
        else:
            return None

    def _scrape_total_matches(self, response):
        total = response.xpath("//div[@id='totalProducts']/text()").extract()
        if total and total[0]:
            total = total[0].replace(',', '').replace('.', '').strip()
            return int(total)
        else:
            self.log("Failed to parse total number of matches.", level=WARNING)
