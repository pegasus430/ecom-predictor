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

class ToysrusSpider(SearchSpider):

    name = "toysrus"

    # initialize fields specific to this derived spider
    def init_sub(self):
        self.target_site = "toysrus"
        self.start_urls = [ "http://www.toysrus.com" ]

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


        # toysrus
        results = hxs.select("//a[@class='prodtitle']")

        for result in results:
            item = SearchItem()
            #item['origin_site'] = site
            item['product_name'] = result.select("text()").extract()[0]
            root_url = "http://www.toysrus.com"
            item['product_url'] = root_url + result.select("@href").extract()[0]

            if 'origin_url' in response.meta:
                item['origin_url'] = response.meta['origin_url']

            items.add(item)

        response.meta['items'] = items
        response.meta['parsed'] = items
        return self.reduceResults(response)
