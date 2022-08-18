import os.path
import re
import urlparse
import requests
import json

import scrapy
from scrapy.http import Request
from scrapy import Selector

from assortment_urls.items import AssortmentUrlsItem

is_empty = lambda x: x[0] if x else None


class MySpider(scrapy.Spider):
    """To run that spider:
    scrapy crawl walmart_urls -o output.json -a file_name=sm.txt
    sm.txt - some file with urls which we need to scrape
    """

    name = 'walmart_urls'
    allowed_domains = ['www.walmart.com']

    current_page = 1

    def __init__(self, *args, **kwargs):
        self.product_url = kwargs['product_url']

        if "num_pages" in kwargs:
            self.num_pages = int(kwargs['num_pages'])
        else:
            self.num_pages = 1  # See https://bugzilla.contentanalyticsinc.com/show_bug.cgi?id=3313#c0

        self.user_agent = "Mozilla/5.0 (X11; Linux i686 (x86_64))" \
            " AppleWebKit/537.36 (KHTML, like Gecko)" \
            " Chrome/37.0.2062.120 Safari/537.36"

    def start_requests(self):
        yield Request(url=self.valid_url(self.product_url))

    def parse(self, response):
        yield self.get_urls(response)
        request = self.next_pagination_link(response)
        if request is not None:
            yield request

    def get_urls(self, response):
        item = AssortmentUrlsItem()
        urls = response.xpath(
            '//li/div/a[contains(@class, "js-product-title")]/@href').extract()

        if not urls:
            urls = response.xpath(
                '//h4[contains(@class, "tile-heading")]/a/@href').extract()
        if not urls:
            urls = response.xpath(
                '//div[contains(@class, "js-product-image-zone")]' \
                '//div[contains(@class, "js-tile tile")]' \
                '/a[1][contains(@class, "tile-section")]' \
                '[contains(@href, "/ip/")]/@href'
            ).extract()

            data = is_empty(re.findall(
                "window._WML.MIDAS_CONTEXT\s+\=\s+([^\;].*)", response.body
            ))
            if data:
                try:
                    data = json.loads(data[0:-1])
                    pageId = is_empty(
                        re.findall("\:(\d+)", data["categoryPathId"]))
                    keyword = data["categoryPathName"]
                except Exception:
                    pass
            if pageId and keyword:
                get_rec = "http://www.walmart.com/msp?"\
                    "&module=wpa&type=product&min=7&max=20"\
                    "&platform=desktop&pageType=category"\
                    "&pageId=%s&keyword=%s" % (pageId, keyword)
                #print "-"*50
                #print get_rec
                #print "-"*50
                resp = requests.get(get_rec)
                urls_get = Selector(text=resp.text).xpath(
                    '//div[contains(@class, "js-module-sponsored-products")]' \
                    '//div[contains(@class, "js-tile tile")]' \
                    '/a[1][contains(@class, "tile-section")]/@href'
                ).extract()
                for url in urls_get:                  
                    r = requests.get(urlparse.urljoin(response.url, url), allow_redirects=True)
                    urls += (r.url, )

        urls = [urlparse.urljoin(response.url, x) for x in urls]
        #print "-"*50
        #print len(urls)
        #print "-"*50
        assortment_url = {response.url: urls}
        item["assortment_url"] = assortment_url
        item['results_per_page'] = self._scrape_results_per_page(response)
        return item

    def _scrape_results_per_page(self, response):
        num = response.css('.result-summary-container ::text').re(
            'Showing (\d+) of')
        if num:
            return int(num[0])

    def next_pagination_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1

        next_link = is_empty(
            response.xpath(
                "//a[contains(@class, 'paginator-btn-next')]/@href"
            ).extract()
        )

        if next_link:
            url = urlparse.urljoin(response.url, next_link)
            return Request(url=url)

    def valid_url(self, url):
        if not re.findall("http(s){0,1}\:\/\/", url):
            url = "http://" + url
        return url