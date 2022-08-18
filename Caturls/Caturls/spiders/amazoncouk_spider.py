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


class AmazoncoukSpider(CaturlsSpider):
    # works for retrieving all products returned by a search.
    # does so by mergeing results of searching in each department.

    name = "amazoncouk"
    allowed_domains = ["amazon.co.uk"]

    # search for Maplin
    #self.start_urls = ["http://www.amazon.co.uk/s/ref=nb_sb_noss_1?url=search-alias%3Daps&field-keywords=Maplin"]

    # gets search results for each department
    def parse(self, response):
        hxs = HtmlXPathSelector(response)
        search_by_department_links = hxs.select("//div[@class='categoryRefinementsSection']/ul/li/a/@href").extract()
        root_url = "http://www.amazon.co.uk"
        
        for link in search_by_department_links:
            yield Request(root_url + link, callback = self.parsePage)


    # parse amazon page and extract product URLs
    def parsePage(self, response):
        hxs = HtmlXPathSelector(response)

        try:
            category = hxs.select("//a[@class='a-link-normal a-color-base a-text-bold a-text-normal']/text()").extract()[0]
        except Exception:
            category = None

        try:
            nr_results = hxs.select("//h2[@id='s-result-count']/text()").re("[0-9,]+")[-1]
            print nr_results, "FOR", category
        except Exception:
            pass

        product_links = hxs.select("//div[contains(@class,'a-row')]//a[contains(@class, 'a-link-normal s-access-detail-page  a-text-normal')]/@href")
        for product_link in product_links:
            item = ProductItem()
            item['product_url'] = product_link.extract()
            item['category'] = category
            yield item

        # select next page, if any, parse it too with this method
        root_url = "http://www.amazon.co.uk"
        next_page = hxs.select("//a[@title='Next Page']/@href").extract()
        
        if next_page:
            page_url = root_url + next_page[0]
            yield Request(url = page_url, callback = self.parsePage)



