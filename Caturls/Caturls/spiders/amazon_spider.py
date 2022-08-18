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
# scrapy crawl amazon -a cat_page="<url>" [-a outfile="<filename>"]
#
################################


class AmazonSpider(CaturlsSpider):

    name = "amazon"
    allowed_domains = ["amazon.com"]

    # amazon televisions
    #self.start_urls = ["http://www.amazon.com/Televisions-Video/b/ref=sa_menu_tv?ie=UTF8&node=1266092011"]

    
    # works for both product list pages and higher level pages with links in the left side menu to the product links page
    def parse(self, response):
        hxs = HtmlXPathSelector(response)
        # select first see more list ("All Televisions")
        seeall = hxs.select("//p[@class='seeMore'][1]/a/@href").extract()
        root_url = "http://www.amazon.com"

        # if we can find see all link, follow it and pass it to parsePage to extract product URLs
        if seeall:
            page_url = root_url + seeall[0]
            return Request(page_url, callback = self.parsePage)

        # otherwise, try to parse current page as product list page
        else:
            return Request(response.url, callback = self.parsePage)


    # parse amazon page and extract product URLs
    def parsePage(self, response):
        hxs = HtmlXPathSelector(response)
        product_links = hxs.select("//h3[@class='newaps']/a/@href")
        for product_link in product_links:
            item = ProductItem()
            item['product_url'] = product_link.extract()
            yield item

        # select next page, if any, parse it too with this method
        root_url = "http://www.amazon.com"
        next_page = hxs.select("//a[@title='Next Page']/@href").extract()
        if next_page:
            page_url = root_url + next_page[0]
            yield Request(url = page_url, callback = self.parsePage)

        # if no products were found, maybe this was a bestsellers page
        if not product_links:
            yield Request(response.url, callback = self.parseBsPage)

            # get next pages as well
            page_urls = hxs.select("//div[@id='zg_paginationWrapper']//a/@href").extract()
            for page_url in page_urls:
                yield Request(page_url, callback = self.parseBsPage)


    # parse bestsellers page for amazon and extract product urls (needed for amazon tablets)
    def parseBsPage(self, response):
        hxs = HtmlXPathSelector(response)
        products = hxs.select("//div[@class='zg_itemImmersion']")

        for product in products:
            item = ProductItem()
            url = product.select("div[@class='zg_itemWrapper']//div[@class='zg_title']/a/@href").extract()
            if url:
                item['product_url'] = url[0].strip()
                yield item


