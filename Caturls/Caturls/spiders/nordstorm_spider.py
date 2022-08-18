from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from scrapy.http import TextResponse
from Caturls.items import ProductItem
from Caturls.spiders.caturls_spider import CaturlsSpider
from pprint import pprint
from scrapy import log

from spiders_utils import Utils

import re
import sys
import json

################################
# Run with 
#
# scrapy crawl nordstorm -a cat_page="<url>" [-a outfile="<filename>"]
#
################################


class NordstormSpider(CaturlsSpider):

    name = "nordstorm"
    allowed_domains = ["shop.nordstorm.com"]

    # # nordstrom sneakers
    #self.start_urls = ["http://shop.nordstrom.com/c/womens-sneakers?dept=8000001&origin=topnav"]

    def parse(self, response):
        hxs = HtmlXPathSelector(response)

        return Request(response.url, callback = self.parsePage)

    # parse nordstrom page and extract URLs
    def parsePage(self, response):
        hxs = HtmlXPathSelector(response)
        root_url = "http://shop.nordstrom.com"

        # extract product URLs
        product_links = hxs.select("//div/a[@class='title']/@href")
        for product_link in product_links:
            item = ProductItem()
            item['product_url'] = root_url + product_link.extract()
            yield item

        # select next page, if any, parse it too with this method
        next_page = hxs.select("//ul[@class='arrows']/li[@class='next']/a/@href").extract()
        if next_page:
            page_url = next_page[0]
            yield Request(url = page_url, callback = self.parsePage)