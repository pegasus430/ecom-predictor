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
# scrapy crawl sonoma -a cat_page="<url>" [-a outfile="<filename>"]
#
################################


class SonomaSpider(CaturlsSpider):

    name = "sonoma"
    allowed_domains = ["williams-sonoma.com"]

    # williams-sonoma blenders
    #self.start_urls = ["http://www.williams-sonoma.com/products/cuisinart-soup-maker-blender-sbc-1000/?pkey=cblenders&"]
    # williams-sonoma mixers
    #self.start_urls = ["http://www.williams-sonoma.com/shop/electrics/mixers-attachments/?cm_type=gnav"]
    # williams-sonoma coffee makers
    #self.start_urls = ["http://www.williams-sonoma.com/shop/electrics/coffee-makers/?cm_type=gnav"]


    def parse(self, response):
        return Request(url = self.cat_page, callback = self.parsePage)

    # parse williams-sonoma page and extract product URLs
    def parsePage(self, response):
        hxs = HtmlXPathSelector(response)
        products = hxs.select("//li[@class='product-cell ']/a")
        items = []

        for product in products:
            item = ProductItem()
            item['product_url'] = product.select("@href").extract()[0]
            items.append(item)

        return items