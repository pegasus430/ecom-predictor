from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from scrapy.http import TextResponse
from scrapy.http import Response
from scrapy.exceptions import CloseSpider
from search.items import SearchItem
from search.spiders.search_spider import SearchSpider
from scrapy import log

from selenium import webdriver
from scrapy.http import TextResponse

from spiders_utils import Utils
from search.matching_utils import ProcessText
import time
import re
import sys

THRESHOLD_LOW = 0.2

class ManufacturerSpider(SearchSpider):

    name = "manufacturer"

    # arbitrary start url
    start_urls = ['http://www.sony.com']

    #threshold = 0.8

    # initialize fields specific to this derived spider
    def init_sub(self):
        #TODO: find a better way for this
        #self.threshold = 0.8
        self.fast = 0
        #self.output = 2

        self.sites_to_parse_methods = {"sony" : self.parseResults_sony, \
                                        "samsung" : self.parseResults_samsung}

        #TODO: close driver on spider close if set
        self.driver = None


    # pass to site-specific parseResults method
    def parseResults(self, response):
        target_site = response.meta['target_site']

        # redo request but don't cache it
        # if target_site == 'samsung':
        #     response.meta['_dont_cache'] = True
#            return Request(response.url, callback=self.parseResults_samsung, meta=response.meta)

        if target_site in self.sites_to_parse_methods:
            return self.sites_to_parse_methods[target_site](response)

    # parse samsung results page
    def parseResults_samsung(self, response):
        hxs = HtmlXPathSelector(response)

        if 'items' in response.meta:
            items = response.meta['items']
        else:
            items = set()

        # add product URLs to be parsed to this list
        if 'search_results' not in response.meta:
            product_urls = set()
        else:
            product_urls = response.meta['search_results']


        #TODO: implement support for multiple results pages?

        
        # if we find any results to this it means we are already on a product page
        results = hxs.select("//ul[@class='product-info']")

        if results:
            product_urls.add(response.url)
            # it also means it's an exact match, so stop search here
            response.meta['pending_requests'] = []
            response.meta['threshold'] = 0.2
            # # also temporarily lower threshold
            # self.threshold = 0.2

        else:

            # try to see if this is a results page then

            # Content seems to be generated with javascript - open page with selenium, extract its content then return it back here
            # try to see if the page contains what we need, or we need to try it with selenium
            results = hxs.select("//input[contains(@id,'detailpageurl')]/@value")
            if not results:
                print 'NO RESULTS: ', response.url

                #results = []

                # COMMENTED FOR TESTING
                # use selenium
                request = self.get_samsung_results(response.url)
                # get body of request
                request_body = request.body
                resp_for_scrapy = TextResponse('none',200,{},request_body,[],None)

                hxs = HtmlXPathSelector(resp_for_scrapy)
                #print "PAGE_SOURCE: ", page_source
                results = hxs.select("//input[contains(@id,'detailpageurl')]/@value")
            else:
                print 'WE ALREADY HAD RESULTS! '
                print 'RESULTS: ', results

            
            for result in results:
                product_url = Utils.add_domain(result.extract().strip(), "http://www.samsung.com")
                product_urls.add(product_url)
            

        if product_urls and ('pending_requests' not in response.meta or not response.meta['pending_requests']):
            request = Request(product_urls.pop(), callback = self.parse_product_samsung, meta = response.meta)
            request.meta['items'] = items

            # this will be the new product_urls list with the first item popped
            request.meta['search_results'] = product_urls

            return request

        # if there were no results, the request will never get back to reduceResults
        else:

            # # we are finished and should close the driver
            # if self.driver:
            #     self.driver.close()

            response.meta['items'] = items
            response.meta['parsed'] = True
            response.meta['search_results'] = product_urls
            # only send the response we have as an argument, no need to make a new request
            return self.reduceResults(response)


    # use selenium to extract samsung results from results page - they are loaded dynamically in a frame, can't be done with scrapy alone
    def get_samsung_results(self, url):

        print 'USED SELENIUM FOR ', url

        # initialize driver if it was not initialized
        if not self.driver:
            self.driver = webdriver.Firefox()

        # use class variable driver, don't open a new one with each request
        self.driver.get(url)

        #time.sleep(5)

        # check if this is a page with a results frame
        if self.driver.find_elements_by_id("searchResult"):
            # switch to results frame
            self.driver.switch_to_frame("searchResult")

        # # click on first <h4>
        # results = driver.find_elements_by_xpath("//h4/a")
        # print "THE RESULTS ARE: ", results
        # results[0].click()

        # convert html to "nice format"
        text_html = self.driver.page_source.encode('utf-8')
        #print "URL: ", url, " TEXT_HTML: ", text_html
        html_str = str(text_html)

        # this is a hack that initiates a "TextResponse" object (taken from the Scrapy module)
        resp_for_scrapy = TextResponse('none',200,{},html_str,[],None)

        #self.driver.close()
    
        #return resp_for_scrapy
        # try to return a request with the received url and the extracted page source in the hope it will get cached
        return Request(url = url, body = html_str, callback = self.parseResults_samsung)
        

    # parse sony results page, extract info for all products returned by search (keep them in "meta")
    def parseResults_sony(self, response):
        hxs = HtmlXPathSelector(response)

        if 'items' in response.meta:
            items = response.meta['items']
        else:
            items = set()

        # add product URLs to be parsed to this list
        if 'search_results' not in response.meta:
            product_urls = set()
        else:
            product_urls = response.meta['search_results']


        #TODO: implement support for multiple results pages?
        results = hxs.select("//h2[@class='ws-product-title fn']//text()")

        # if we find any results to this it means we are already on a product page
        if results:
            #TODO: only works when queries with product model, but in original form, that is, with caps
            product_urls.add(response.url)
            # it also means it's an exact match, so stop search here
            response.meta['pending_requests'] = []
            # also set threshold to lower value
            response.meta['threshold'] = THRESHOLD_LOW

        else:
            #TODO
            # try to see if this is a results page then
            results = hxs.select("//h5[@class='ws-product-title fn']")
            for result in results:
                product_url = result.select("parent::node()//@href").extract()[0]
                product_urls.add(product_url)

        if product_urls and ('pending_requests' not in response.meta or not response.meta['pending_requests']):
            request = Request(product_urls.pop(), callback = self.parse_product_sony, meta = response.meta)
            request.meta['items'] = items

            # this will be the new product_urls list with the first item popped
            request.meta['search_results'] = product_urls

            return request

        # if there were no results, the request will never get back to reduceResults
        else:
            response.meta['items'] = items
            response.meta['parsed'] = True
            response.meta['search_results'] = product_urls
            # only send the response we have as an argument, no need to make a new request
            return self.reduceResults(response)


        # parse product page on samsung.com
    def parse_product_samsung(self, response):

        hxs = HtmlXPathSelector(response)

        items = response.meta['items']

        #site = response.meta['origin_site']
        origin_url = response.meta['origin_url']

        # create item
        item = SearchItem()
        item['product_url'] = response.url
        item['origin_url'] = origin_url
        item['origin_name'] = response.meta['origin_name']
        # hardcode brand to sony
        item['product_brand'] = 'samsung'

        # extract product name, brand, model, etc; add to items
        product_info = hxs.select("//ul[@class='product-info']")
        #TODO: for some products name is not extracted correctly
        product_name = product_info.select("meta[@itemprop='name']/@content")
        if not product_name:
            self.log("Error: No product name: " + str(response.url), level=log.INFO)
        else:
            item['product_name'] = product_name.extract()[0]
            product_model = product_info.select("meta[@itemprop='model']/@content")
            if product_model:
                item['product_model'] = product_model.extract()[0]

            #TODO
            # item['product_images'] = 
            # #TODO: to check
            # item['product_videos'] = l

            items.add(item)


        # if there are any more results to be parsed, send a request back to this method with the next product to be parsed
        product_urls = response.meta['search_results']

        if product_urls:
            request = Request(product_urls.pop(), callback = self.parse_product_samsung, meta = response.meta)
            request.meta['items'] = items
            # eliminate next product from pending list (this will be the new list with the first item popped)
            request.meta['search_results'] = product_urls

            return request
        else:
            # otherwise, we are done, send a the response back to reduceResults (no need to make a new request)

            # # we are finished so we should also close the driver
            # if self.driver:
            #     self.driver.close()

            response.meta['parsed'] = True
            response.meta['items'] = items

            return self.reduceResults(response)


    # parse product page on sony.com
    def parse_product_sony(self, response):
        hxs = HtmlXPathSelector(response)

        items = response.meta['items']

        #site = response.meta['origin_site']
        origin_url = response.meta['origin_url']

        # create item
        item = SearchItem()
        item['product_url'] = response.url
        item['origin_url'] = origin_url
        # hardcode brand to sony
        item['product_brand'] = 'sony'

        # extract product name, brand, model, etc; add to items
        product_name = hxs.select("//h2[@class='ws-product-title fn']//text()")
        if not product_name:
            self.log("Error: No product name: " + str(response.url), level=log.INFO)
        else:
            item['product_name'] = product_name.extract()[0]
        product_model = hxs.select("//span[@class='ws-product-item-number-value item-number']/text()")
        if product_model:
            item['product_model'] = product_model.extract()[0]

        item['product_images'] = len(hxs.select("//a[@class='ws-alternate-views-list-link']/img").extract())
        item['product_videos'] = len(hxs.select("//li[@class='ws-video']//img").extract())

        items.add(item)


        # if there are any more results to be parsed, send a request back to this method with the next product to be parsed
        product_urls = response.meta['search_results']

        if product_urls:
            request = Request(product_urls.pop(), callback = self.parse_product_sony, meta = response.meta)
            request.meta['items'] = items
            # eliminate next product from pending list (this will be the new list with the first item popped)
            request.meta['search_results'] = product_urls

            return request
        else:
            # otherwise, we are done, send a the response back to reduceResults (no need to make a new request)

            response.meta['parsed'] = True
            response.meta['items'] = items

            return self.reduceResults(response)

