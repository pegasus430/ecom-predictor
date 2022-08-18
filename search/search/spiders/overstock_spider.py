from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from scrapy.http import TextResponse
from scrapy.http import Response
from scrapy.exceptions import CloseSpider
from search.items import SearchItem
from search.spiders.search_spider import SearchSpider
from scrapy import log

from spiders_utils import Utils
from search.matching_utils import ProcessText

import re
import sys

class OverstockSpider(SearchSpider):

    name = "overstock"

    # initialize fields specific to this derived spider
    def init_sub(self):
        self.target_site = "overstock"
        self.start_urls = [ "http://www.overstock.com" ]

    def parseResults(self, response):

        hxs = HtmlXPathSelector(response)

        #site = response.meta['origin_site']
        origin_name = response.meta['origin_name']
        origin_model = response.meta['origin_model']

        # if this comes from a previous request, get last request's items and add to them the results

        if 'items' in response.meta:
            items = response.meta['items']
        else:
            items = set()



        results = hxs.select("//li[@class='product']/div[@class='product-content']/a[@class='pro-thumb']")
        for result in results:
            item = SearchItem()
            #item['origin_site'] = site
            item['product_name'] = result.select("span[@class='pro-name']/text()").extract()[0]
            item['product_url'] = result.select("@href").extract()[0]

            if 'origin_url' in response.meta:
                item['origin_url'] = response.meta['origin_url']

            items.add(item)

        response.meta['items'] = items
        response.meta['parsed'] = items
        return self.reduceResults(response)
