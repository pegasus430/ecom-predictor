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

class SearchResultsSpider(SearchSpider):


    # create product items from results using only results pages (extracting needed info on products from there)
    # parse results page, extract info for all products returned by search (keep them in "meta")
    def parseResults(self, response):
        hxs = HtmlXPathSelector(response)

        origin_product_id = response.meta['origin_product_id']
        current_query = response.meta['query']

        # all product urls from all queries
        items = sum(map(lambda q: self.results[origin_product_id]['search_requests'][q]['product_items'], \
            self.results[origin_product_id]['search_requests']), [])

        result_items = self.extract_result_products(response)
        for item in result_items:

            for field in self.results[origin_product_id]['origin_product'].keys():
                item[field] = self.results[origin_product_id]['origin_product'][field]

            # extract product model from name
            product_model_extracted = ProcessText.extract_model_from_name(item['product_name'])
            if product_model_extracted:
                item['product_model'] = product_model_extracted

            
            # add result to items
            self.results[origin_product_id]['search_requests'][current_query]['product_items'].append(item)

        # extract product info from product pages (send request to parse first URL in list)
        # add as meta all that was received as meta, will pass it on to reduceResults function in the end
        # also send as meta the entire results list (the product pages URLs), will receive callback when they have all been parsed

        # send the request back to reduceResults (with updated 'items') whether there are any more pending requests or not
        # if there are, reduceResults will send the next one back here, if not it will return the final result

        # and field 'parsed' to indicate that the call was received from this method (was not the initial one)
        #TODO: do we still need this?
        response.meta['parsed'] = True
        # only send the response we have as an argument, no need to make a new request
        return self.reduceResults(response)

    def extract_results_products(self, response):
        '''Abstract method to be overridden by derived classes.
        Receives response of search results page
        and returns list of product items in the search results,
        with all the extracted info from each from the search results page
        '''
        return []

