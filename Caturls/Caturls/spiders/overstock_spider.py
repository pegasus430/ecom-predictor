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
# scrapy crawl overstock -a cat_page="<url>" [-a outfile="<filename>"]
#
################################


class OverstockSpider(CaturlsSpider):

    name = "overstock"
    allowed_domains = ["overstock.com"]

    # overstock tablets
    #self.start_urls = ["http://www.overstock.com/Electronics/Tablet-PCs/New,/condition,/24821/subcat.html?TID=TN:ELEC:Tablet"]

    #TODO: is the list of product numbers ok for all pages? got if from laptops category request, seems to work for others as well even though it's not the same
    def parse(self, response):
        # # get category, and if it's laptops treat it specially using the hardcoded url
        # m = re.match("http://www.overstock.com/[^/]+/([^/]+)/.*", self.cat_page)
        # if m and m.group(1) == "Laptops":
        return Request(url = self.cat_page + "&index=1&count=25&products=7516115,6519070,7516111,7646312,7382330,7626684,8086492,8233094,7646360,8135172,6691004,8022278&infinite=true", callback = self.parsePage, \
            headers = {"Referer": self.cat_page + "&page=2", "X-Requested-With": "XMLHttpRequest"}, \
            meta = {"index" : 1})
        # else:
        #     return Request(url = self.cat_page, callback = self.parsePage)


    # parse overstock page and extract URLs
    def parsePage(self, response):
        hxs = HtmlXPathSelector(response)

        product_links = hxs.select("//a[@class='pro-thumb']/@href")
        items = []
        for product_link in product_links:
            item = ProductItem()
            url = product_link.extract()

            # remove irrelevant last part of url
            m = re.match("(.*product\.html)\?re.*", url)
            if m:
                url = m.group(1)
            item['product_url'] = url
            yield item

        # get next pages, stop when you find no more product urls
        # url = http://www.overstock.com/Electronics/Laptops/133/subcat.html?index=101&sort=Top+Sellers&TID=SORT:Top+Sellers&count=25&products=7516115,6519070,7516111,7646312,7382330,7626684,8086492,8233094,7646360,8135172,6691004,8022278&infinite=true
        if product_links:
            # # get category, and if it's laptops treat it specially using the hardcoded url
            # m = re.match("http://www.overstock.com/[^/]+/([^/]+)/.*", self.cat_page)
            # if m and m.group(1) == "Laptops":
            # parse next pages as well
            index = int(response.meta['index']) + 25
            yield Request(url = self.cat_page + "&index=" + str(index) + "&count=25&products=7516115,6519070,7516111,7646312,7382330,7626684,8086492,8233094,7646360,8135172,6691004,8022278&infinite=true", callback = self.parsePage, \
                    headers = {"Referer": self.cat_page + "&page=2", "X-Requested-With": "XMLHttpRequest"}, \
                    meta = {"index" : index})
                

                #TODO: same thing for other categories?