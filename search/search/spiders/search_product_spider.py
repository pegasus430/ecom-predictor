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

'''Generic spider for target sites, that uses info extracted
from the product page.
To be used as parent class for new target sites.
'''

class SearchProductSpider(SearchSpider):

    def parseResults(self, response):

        origin_product_id = response.meta['origin_product_id']
        current_query = response.meta['query']

        origin_name = self.results[origin_product_id]['origin_product']['origin_name']
        origin_url = self.results[origin_product_id]['origin_product']['origin_url']

        # all product urls from all queries
        items = sum(map(lambda q: self.results[origin_product_id]['search_requests'][q]['product_items'], \
            self.results[origin_product_id]['search_requests']), [])
        # all product urls from all queries
        product_urls = sum(map(lambda q: self.results[origin_product_id]['search_requests'][q]['search_results'], \
            self.results[origin_product_id]['search_requests']), [])
        product_urls = set(product_urls)

        results = self.extract_results(response)
        for result in results:
            self.results[origin_product_id]['search_requests'][current_query]['search_results'].append(result)
 
        # extract product info from product pages (send request to parse first URL in list)
        # add as meta all that was received as meta, will pass it on to reduceResults function in the end
        # also send as meta the entire results list (the product pages URLs), will receive callback when they have all been parsed

        # send the request further to parse product pages only if we gathered all the product URLs from all the queries 
        # (there are no more pending requests)
        # otherwise send them back to parseResults and wait for the next query, save all product URLs in search_results
        # this way we avoid duplicates
        if product_urls and ('pending_requests' not in response.meta or not response.meta['pending_requests']):
            next_product_url = product_urls.pop() 
            request = Request(next_product_url, callback = self.parse_product, meta = response.meta)
            self.remove_result_from_queue(origin_product_id, next_product_url)

            return request

        # if there were no results, the request will never get back to reduceResults
        # so send it from here so it can parse the next queries
        # add to the response the URLs of the products to crawl we have so far, items (handles case when it was not created yet)
        # and field 'parsed' to indicate that the call was received from this method (was not the initial one)
        else:
            response.meta['parsed'] = True

            # only send the response we have as an argument, no need to make a new request

            # print "RETURNING TO REDUCE RESULTS", response.meta['origin_url']
            return self.reduceResults(response)


        # relevant for extracting products from results page only
        # - deprecated
        # response.meta['items'] = items
        # response.meta['parsed'] = items
        # return self.reduceResults(response)
    
    # extract product info from a product page
    # keep product pages left to parse in 'search_results' meta key, send back to parseResults_new when done with all
    def parse_product(self, response):

        # redirect pages, if handled, can return empty bodies
        # especially for kohls
        if not response.body:
            self.log("Retried empty page: " + response.url, level=log.WARNING)
            return Request(response.url, callback = self.parse_product, meta=response.meta)

        # try to avoid mobile versions
        # especially for kohls
        if response.url.startswith("http://m."):
            meta = response.meta
            meta['dont_redirect'] = True
            url = re.sub("/m\.","/www.",response.url)
            self.log("Retrying: redirecting mobile page to www page", level=log.WARNING)
            return Request(url, callback=self.parse_product, meta=meta)

        origin_product_id = response.meta['origin_product_id']
        current_query = response.meta['query']
        origin_url = self.results[origin_product_id]['origin_product']['origin_url']

        item = SearchItem()
        item['product_url'] = response.url
        for field in self.results[origin_product_id]['origin_product'].keys():
            item[field] = self.results[origin_product_id]['origin_product'][field]
        

        # all product urls from all queries
        items = sum(map(lambda q: self.results[origin_product_id]['search_requests'][q]['product_items'], \
            self.results[origin_product_id]['search_requests']), [])
        # all product urls from all queries
        product_urls = sum(map(lambda q: self.results[origin_product_id]['search_requests'][q]['search_results'], \
            self.results[origin_product_id]['search_requests']), [])
        product_urls = set(product_urls)

        item = self.extract_product_data(response, item)

        # add result to items (if it was successful)
        if item:
            self.results[origin_product_id]['search_requests'][current_query]['product_items'].append(item)

        # try to send request to parse next product, try until url for next product url is valid (response not 404)
        # this is needed because if next product url is not valid, this request will not be sent and all info about this match (stored in request meta) will be lost

        # find first valid next product url
        next_product_url = None
        if product_urls:
            next_product_url = product_urls.pop()

        # if a next product url was found, send new request back to parse_product_url
        if next_product_url:
            request = Request(next_product_url, callback = self.parse_product, meta = response.meta)
            # eliminate next product from pending list (this will be the new list with the first item popped)
            self.remove_result_from_queue(origin_product_id, next_product_url)

            return request

        # if no next valid product url was found
        else:
            # we are done, send a the response back to reduceResults (no need to make a new request)
            # add as meta newly added items
            # also add 'parsed' field to indicate that the parsing of all products was completed and they cand be further used
            # (actually that the call was made from this method and was not the initial one, so it has to move on to the next request)

            response.meta['parsed'] = True

            return self.reduceResults(response)

    def extract_results(self, response):
        '''Abstract method to be overridden by derived classes.
        Receives response of search results page
        and returns list of product urls in the search results
        '''
        return []

    def extract_product_data(self, response, item):
        '''Abstract method to be overridden by derived classes.
        Receives response of product page and the product's item
        and returns the modified product item containing all the extracted data
        (name, brand, price, model, upc etc)
        '''
        return item
