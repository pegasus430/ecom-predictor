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


class TescoSpider(SearchSpider):

    name = "tesco"
    # initialize fields specific to this derived spider
    def init_sub(self):
        self.target_site = "tesco"
        self.start_urls = [ "http://www.tesco.com" ]

        self.base_url = "http://www.tesco.com"


    # create product items from results using only results pages (extracting needed info on products from there)
    # parse results page for tesco, extract info for all products returned by search (keep them in "meta")
    def parseResults(self, response):
        hxs = HtmlXPathSelector(response)

        if 'items' in response.meta:
            items = response.meta['items']
        else:
            items = set()

        results = hxs.select("//ul[@class='products']//div[@class='product ']//h3//a")
        for result in results:
            item = SearchItem()

            product_url = result.select("@href").extract()[0] if result.select("@href") else None
            product_name = result.select("@title").extract()[0] if result.select("@title") else None

            # assert name is not abbreviated
            # empirically, this only seems to produce false positives, so removed
            # assert '...' not in product_name

            # quit if there is no product name
            if product_name and product_url:
                # clean url
                item['product_url'] = Utils.add_domain(product_url, self.base_url)
                
                item['product_name'] = product_name
            else:
                self.log("No product name: " + str(response.url) + " from product: " + response.meta['origin_url'], level=log.ERROR)
                continue

            # add url, name and model of product to be matched (from origin site)
            item['origin_url'] = response.meta['origin_url']
            item['origin_name'] = response.meta['origin_name']

            if 'origin_model' in response.meta:
                item['origin_model'] = response.meta['origin_model']

            # extract product model from name
            product_model_extracted = ProcessText.extract_model_from_name(item['product_name'])
            if product_model_extracted:
                item['product_model'] = product_model_extracted

            #TODO: extract: price, brand?

            # add result to items
            items.add(item)


        # extract product info from product pages (send request to parse first URL in list)
        # add as meta all that was received as meta, will pass it on to reduceResults function in the end
        # also send as meta the entire results list (the product pages URLs), will receive callback when they have all been parsed

        # send the request back to reduceResults (with updated 'items') whether there are any more pending requests or not
        # if there are, reduceResults will send the next one back here, if not it will return the final result

        response.meta['items'] = items

        # and field 'parsed' to indicate that the call was received from this method (was not the initial one)
        #TODO: do we still need this?
        response.meta['parsed'] = True
        # only send the response we have as an argument, no need to make a new request
        return self.reduceResults(response)

