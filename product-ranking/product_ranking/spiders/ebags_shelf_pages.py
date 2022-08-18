import re
import urlparse
import random
import hjson

import requests
from lxml import html
import scrapy
from scrapy.log import WARNING, ERROR
from scrapy.http import Request

from product_ranking.items import SiteProductItem

is_empty = lambda x: x[0] if x else None

from .ebags import EbagsProductsSpider


class EbagsShelfPagesSpider(EbagsProductsSpider):
    name = 'ebags_shelf_urls_products'
    allowed_domains = ["ebags.com", "www.ebags.com"]  # without this find_spiders() fails
    # Browser agent string list
    BROWSER_AGENT_STRING_LIST = {"Firefox": ["Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1",
                                             "Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0",
                                             "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10; rv:33.0) Gecko/20100101 Firefox/33.0"],
                                 "Chrome":  ["Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36",
                                             "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.1 Safari/537.36",
                                             "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.0 Safari/537.36",
                                             "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.0 Safari/537.36"],
                                 "Safari":  ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.75.14 (KHTML, like Gecko) Version/7.0.3 Safari/7046A194A",
                                             "Mozilla/5.0 (iPad; CPU OS 6_0 like Mac OS X) AppleWebKit/536.26 (KHTML, like Gecko) Version/6.0 Mobile/10A5355d Safari/8536.25",
                                             "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/537.13+ (KHTML, like Gecko) Version/5.1.7 Safari/534.57.2"]
                                 }

    def _select_browser_agents_randomly(self, agent_type=None):
        if agent_type and agent_type in self.BROWSER_AGENT_STRING_LIST:
            return random.choice(self.BROWSER_AGENT_STRING_LIST[agent_type])

        return random.choice(random.choice(self.BROWSER_AGENT_STRING_LIST.values()))

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
        super(EbagsShelfPagesSpider, self).__init__(*args, **kwargs)
        self._setup_class_compatibility()

        self.product_url = kwargs['product_url']

        if "num_pages" in kwargs:
            self.num_pages = int(kwargs['num_pages'])
        else:
            self.num_pages = 1  # See https://bugzilla.contentanalyticsinc.com/show_bug.cgi?id=3313#c0

        self.user_agent = "Mozilla/5.0 (X11; Linux i686 (x86_64))" \
            " AppleWebKit/537.36 (KHTML, like Gecko)" \
            " Chrome/37.0.2062.120 Safari/537.36"

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
                      meta=self._setup_meta_compatibility())  # meta is for SC baseclass compatibility

    def _scrape_product_links(self, response):
        urls = response.xpath(
            '//div[@id="serverResultsList"]//div[contains(@class,"listPageImage")]/a/@href'
        ).extract()
        urls = ['http://www.ebags.com'+x for x in urls]

        # parse shelf category
        shelf_categories = response.xpath(
            '//ul[@id="breadcrumbList"]//li[not(@id="homeBreadcrumb")]/a/text()'
        ).extract()

        shelf_categories = [category.strip() for category in shelf_categories]
        shelf_categories = filter(None, shelf_categories)
        for url in urls:
            item = SiteProductItem()
            if shelf_categories:
                if shelf_categories:
                    item['shelf_name'] = shelf_categories[-1]
                    item['shelf_path'] = shelf_categories
            yield url, item

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        return super(EbagsShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)

    def parse_product(self, response):
        return super(EbagsShelfPagesSpider, self).parse_product(response)
