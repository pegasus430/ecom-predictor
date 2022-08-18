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

class MaplinSpider(SearchSpider):

    name = "maplin"
    # allow 404 so that it doesn't break the entire flow when one is encountered.
    # Example: maplin search results pages when no results were found
    handle_httpstatus_list = [404]

    # initialize fields specific to this derived spider
    def init_sub(self):
        self.target_site = "maplin"
        self.start_urls = [ "http://www.maplin.co.uk" ]

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

        # add product URLs to be parsed to this list
        if 'search_results' not in response.meta:
            product_urls = set()
        else:
            product_urls = response.meta['search_results']


        # TODO: check this xpath and extractions
        results = hxs.select("//div[@class='tileinfo']/a")

        for result in results:

            product_url = result.select("@href").extract()[0]
            product_url = Utils.add_domain(product_url, "http://www.maplin.co.uk")
            product_urls.add(product_url)

 
        # extract product info from product pages (send request to parse first URL in list)
        # add as meta all that was received as meta, will pass it on to reduceResults function in the end
        # also send as meta the entire results list (the product pages URLs), will receive callback when they have all been parsed

        # send the request further to parse product pages only if we gathered all the product URLs from all the queries 
        # (there are no more pending requests)
        # otherwise send them back to parseResults and wait for the next query, save all product URLs in search_results
        # this way we avoid duplicates
        if product_urls and ('pending_requests' not in response.meta or not response.meta['pending_requests']):
            request = Request(product_urls.pop(), callback = self.parse_product_maplin, meta = response.meta)
            request.meta['items'] = items

            # this will be the new product_urls list with the first item popped
            request.meta['search_results'] = product_urls

            return request

        # if there were no results, the request will never get back to reduceResults
        # so send it from here so it can parse the next queries
        # add to the response the URLs of the products to crawl we have so far, items (handles case when it was not created yet)
        # and field 'parsed' to indicate that the call was received from this method (was not the initial one)
        else:
            response.meta['items'] = items
            response.meta['parsed'] = True
            response.meta['search_results'] = product_urls
            # only send the response we have as an argument, no need to make a new request

            # print "RETURNING TO REDUCE RESULTS", response.meta['origin_url']
            return self.reduceResults(response)


        # relevant for extracting products from results page only
        # - deprecated
        # response.meta['items'] = items
        # response.meta['parsed'] = items
        # return self.reduceResults(response)
    
    # extract product info from a product page for maplin
    # keep product pages left to parse in 'search_results' meta key, send back to parseResults_new when done with all
    def parse_product_maplin(self, response):

        hxs = HtmlXPathSelector(response)

        items = response.meta['items']

        #site = response.meta['origin_site']
        origin_url = response.meta['origin_url']

        item = SearchItem()
        item['product_url'] = response.url
        #item['origin_site'] = site
        item['origin_url'] = origin_url
        item['origin_name'] = response.meta['origin_name']

        if 'origin_model' in response.meta:
            item['origin_model'] = response.meta['origin_model']
        if 'origin_upc' in response.meta:
            item['origin_upc'] = response.meta['origin_upc']
        if 'origin_brand' in response.meta:
            item['origin_brand'] = response.meta['origin_brand']


        product_name_node = hxs.select("//h1[@itemprop='name']/text()").extract()
        if product_name_node:
            product_name = product_name_node[0].strip()
        else:
            self.log("Error: No product name: " + str(response.url) + " for source product " + origin_url, level=log.ERROR)
            # TODO:is this ok? I think so
            return

        item['product_name'] = product_name

        # extract product model number
        # TODO: no model?
        # TODO: no upc?
        # TODO: no brand?
        # TODO: add code extraction
        
        # extract price
        price_holder = hxs.select("//meta[@itemprop='price']/@content").extract()
        # if we can't find it like above try other things:
        if price_holder:
            product_target_price = price_holder[0].strip()
            # remove commas separating orders of magnitude (ex 2,000)
            product_target_price = re.sub(",","",product_target_price)
            try:
                product_target_price = float(product_target_price)

                # convert to dollars (assume pounds)
                product_target_price = Utils.convert_to_dollars(product_target_price, u'\xa3')
                item['product_target_price'] = product_target_price
            except Exception, ex:
                self.log("Couldn't convert product price: " + response.url + "\n", level=log.WARNING)

        else:
            self.log("Didn't find product price: " + response.url + "\n", level=log.INFO)


        # add result to items
        items.add(item)


        product_urls = response.meta['search_results']

        # try to send request to parse next product, try until url for next product url is valid (response not 404)
        # this is needed because if next product url is not valid, this request will not be sent and all info about this match (stored in request meta) will be lost

        # find first valid next product url
        next_product_url = None
        if product_urls:
            next_product_url = product_urls.pop()

        # if a next product url was found, send new request back to parse_product_url
        if next_product_url:
            request = Request(next_product_url, callback = self.parse_product_maplin, meta = response.meta)
            request.meta['items'] = items
            # eliminate next product from pending list (this will be the new list with the first item popped)
            request.meta['search_results'] = product_urls

            return request

        # if no next valid product url was found
        else:
            # we are done, send a the response back to reduceResults (no need to make a new request)
            # add as meta newly added items
            # also add 'parsed' field to indicate that the parsing of all products was completed and they cand be further used
            # (actually that the call was made from this method and was not the initial one, so it has to move on to the next request)

            response.meta['parsed'] = True
            response.meta['items'] = items

            return self.reduceResults(response)


