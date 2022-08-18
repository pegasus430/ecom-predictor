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
# scrapy crawl bestbuy -a cat_page="<url>" [-a outfile="<filename>"]
#
################################


class BestbuySpider(CaturlsSpider):

    name = "bestbuy"
    allowed_domains = ["bestbuy.com"]

    # bestbuy televisions
    #self.start_urls = ["http://www.bestbuy.com/site/Electronics/Televisions/pcmcat307800050023.c?id=pcmcat307800050023&abtest=tv_cat_page_redirect"]

    # works for both product list pages and higher level pages with links in the left side menu to the product links page
    def parse(self, response):
        hxs = HtmlXPathSelector(response)

        # try to see if it's not a product page but branches into further subcategories, select "See all..." page URL
        seeall_list = hxs.select("//ul[@class='search']")
        if seeall_list:
            seeall = seeall_list[0].select("li[1]/a/@href").extract()
            if seeall:
                root_url = "http://www.bestbuy.com"
                page_url = root_url + seeall[0]

                # send the page to parsePage and extract product URLs
                return Request(page_url, callback = self.parsePage)

            else:
                return Request(response.url, callback = self.parsePage)

        # if you can't find the link to the product list page, try to parse this as the product list page
        else:
            return Request(response.url, callback = self.parsePage)


    # parse bestbuy page and extract product URLs
    def parsePage(self, response):
        hxs = HtmlXPathSelector(response)
        root_url = "http://www.bestbuy.com"

        # extract product URLs
        product_links = hxs.select("//div[@class='info-main']/h3/a/@href")
        for product_link in product_links:
            item = ProductItem()
            item['product_url'] = root_url + product_link.extract()
            yield item

        # select next page, if any, parse it too with this method
        next_page = hxs.select("//ul[@class='pagination']/li/a[@class='next']/@href").extract()
        if next_page:
            page_url = root_url + next_page[0]
            yield Request(url = page_url, callback = self.parsePage_bestbuy)



