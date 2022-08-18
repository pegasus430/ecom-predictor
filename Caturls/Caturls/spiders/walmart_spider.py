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
# scrapy crawl walmart -a cat_page="<url>" [-a outfile="<filename>"]
#
################################


class WalmartSpider(CaturlsSpider):

    name = "walmart"
    allowed_domains = ["walmart.com"]

    # walmart televisions
    #self.start_urls = ["http://www.walmart.com/cp/televisions-video/1060825?povid=P1171-C1110.2784+1455.2776+1115.2956-L13"]

    # works for both product list pages and higher level pages with links in the left side menu to the product links page
    def parse(self, response):
        hxs = HtmlXPathSelector(response)

        # try to see if it's not a product page but branches into further subcategories, select "See all..." page URL
        #! this has a space after the div class, maybe in other pages it doesn't
        seeall = hxs.select("//div[@class='CustomSecondaryNav ']//li[last()]/a/@href").extract()
        if seeall:
            root_url = "http://www.walmart.com"
            page_url = root_url + seeall[0]
            # send the page to parsePage and extract product URLs
            request = Request(page_url, callback = self.parsePage)
            return request
        # if you can't find the link to the product list page, try to parse this as the product list page
        else:
            return Request(response.url, callback = self.parsePage)


    # parse walmart page and extract product URLs
    def parsePage(self, response):
        hxs = HtmlXPathSelector(response)
        root_url = "http://www.walmart.com"
        product_links = hxs.select("//a[@class='prodLink ListItemLink']/@href")

        for product_link in product_links:
            item = ProductItem()
            item['product_url'] = root_url + product_link.extract()
            yield item

        # select next page, if any, parse it too with this method
        next_page = hxs.select("//a[@class='link-pageNum' and text()=' Next ']/@href").extract()
        if next_page:
            page_url = root_url + next_page[0]
            yield Request(url = page_url, callback = self.parsePage)

