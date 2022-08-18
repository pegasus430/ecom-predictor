from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from scrapy.spider import BaseSpider
from scrapy.http import TextResponse
from scrapy.http import Response
from scrapy.exceptions import CloseSpider
from search.items import SearchItem
from scrapy import log

from spiders_utils import Utils
from search.matching_utils import ProcessText

import re
import sys
import json
import csv
import urllib
import uuid

import cv2

# from selenium import webdriver
# import time

################################
# Run with 
#
#   scrapy crawl <site> -a product_name="<name>" [-a output="<option(1/2)>"] [-a threshold=<value>] [a outfile="<filename>"] [-a fast=0]
#      -- or --
#   scrapy crawl <site> -a product_url="<url>" [-a output="<option(1/2)>"] [-a threshold=<value>] [a outfile="<filename>""] [-a fast=0]
#      -- or --
#   scrapy crawl <site> -a product_urls_file="<filename>" [-a output="<option(1/2)>"] [-a threshold=value] [a outfile="<filename>"] [-a fast=0]
# 
# where <site> is the derived spider corresponding to the site to search on 
#
# Usage example:
#
# scrapy crawl amazon -a product_urls_file="../sample_output/walmart_televisions_urls.txt" -a output=2 -a outfile="search_results_1.4.txt" -a threshold=1.4 -s LOG_ENABLED=1 2>search_log_1.4.out
#
################################


# search for a product in all sites, using their search functions; give product as argument by its name or its page url
class SearchSpider(BaseSpider):

    name = "search"

    allowed_domains = ["amazon.com", "walmart.com", "bloomingdales.com", "overstock.com", "wayfair.com", "bestbuy.com", "toysrus.com",\
                       "bjs.com", "sears.com", "staples.com", "newegg.com", "ebay.com", "target.com", "sony.com", "samsung.com", \
                       "boots.com", "ocado.com", "tesco.com", "maplin.co.uk", "amazon.co.uk", "currys.co.uk", "pcworld.co.uk", "ebay.co.uk", \
                       "argos.co.uk", "ebuyer.com", "ebuyer.co.uk", "firebox.com", "rakuten.co.uk", "uk.rs-online.com", "screwfix.com",
                       "macys.com", "kohls.com"]

    # pass product as argument to constructor - either product name or product URL
    # arguments:
    #                product_name - the product's name, for searching by product name
    #                product_url - the product's page url in the source site, for searching by product URL
    #                product_urls_file - file containing a list of product pages URLs
    #                bestsellers_link - link to list of bestseller products
    #                output - integer(1/2/3/4) option indicating output type (either result URL (1), or result URL and source product URL (2))
    #                         3 - same as 2 but with extra field representing confidence score
    #                         4 - same as 3 but with origin products represented by UPC instead of URL
    #                         5 - same as 3 but with product name as well, on first column (name from source site)
    #                         6 - same as 3 but additionally with bestsellers rank (origin and target) - to be used
    #                             in combination with the input bestsellers_link option
    #                         7 - completely custom, using list of output fields in fields.json
    #                threshold - parameter for selecting results (the lower the value the more permissive the selection)
    def __init__(self, product_name = None, products_file = None, product_url = None, product_urls_file = None, bestsellers_link = None, bestsellers_range = '0', \
        output = 2, threshold = 1.0, \
        outfile = "search_results.csv", outfile2 = "not_matched.csv", fast = 0, use_proxy = False, manufacturer_site = None):

        # call specific init for each derived class
        self.init_sub()

        self.version = "3eccc771a21f33b55f9267042a7a40ea0eb6013f"

        self.product_url = product_url
        self.products_file = products_file
        self.product_name = product_name
        self.bestsellers_link = bestsellers_link
        self.bestsellers_range = self.parse_bestsellers_range(bestsellers_range)
        self.output = int(output)
        self.product_urls_file = product_urls_file
        self.threshold = float(threshold)
        self.outfile = outfile
        self.outfile2 = outfile2
        self.fast = fast
        self.use_proxy = use_proxy
        self.manufacturer_site = manufacturer_site

        # parseURL functions, one for each supported origin site
        self.parse_url_functions = {'staples' : self.parseURL_staples, \
                                    'walmart' : self.parseURL_walmart, \
                                    'newegg' : self.parseURL_newegg,\
                                    'boots' : self.parseURL_boots, \
                                    'ocado' : self.parseURL_ocado, \
                                    'tesco' : self.parseURL_tesco, \
                                    'amazon' : self.parseURL_amazon, \
                                    'target' : self.parseURL_target, \
                                    'maplin' : self.parseURL_maplin, \
                                    'wayfair' : self.parseURL_wayfair
                                    }

        # parse_bestsellers functions, for each supported origin site
        self.parse_bestsellers_functions = {'amazon' : self.parse_bestsellers_amazon, \
                                            'walmart' : self.parse_bestsellers_walmart
                                            }

        '''this dictionary will store all input products, search requests and output products as they
        flow thorugh the callbacks up to when the match is found
        keys are uuids that represent an input product
        values are dictionaries that have search queries as keys and candidates as values
        candidates will be separated into 2 lists: search results, that contain the search
        result urls that have not been processed, and product items, that contain the already extracted items
        example:
        {
            '27c54eaa28354c3db1c9f71ef161a2f0': {
                'search_requests': {
                    '035000741288': {
                        'product_items': [],
                        'search_results': []
                    }
                }, {
                    'b001kys2ua': {
                        'product_items': [],
                        'search_results': []
                    }
                }, {
                    'b001kys2ua+colgate': {
                        'product_items': [],
                        'search_results': []
                    }
                }, {
                    'colgate+total+whitening+toothpaste+twin+pk+two+6oz+tubes': {
                        'product_items': [],
                        'search_results': []
                    }
                }, {
                    'colgate+total': {
                        'product_items': [],
                        'search_results': []
                    }
                }, {
                    'toothpaste+total': {
                        'product_items': [],
                        'search_results': []
                    }
                },
                'origin_product': {
                    'origin_model': 'B001KYS2UA',
                    'origin_brand_extracted': 'colgate',
                    'origin_name': 'Colgate Total Whitening Toothpaste Twin Pack (two 6oz tubes)',
                    'origin_url': 'http://www.amazon.com/Colgate-Total-Whitening-Toothpaste-tubes/dp/B001KYS2UA',
                    'origin_brand': 'Colgate',
                    'origin_manufacturer_code': None,
                    'origin_upc': ['035000741288'],
                    'origin_price': 4.74
                }
            }
        }

        '''
        self.results = {}


    def build_search_pages(self, search_query):
        # build list of urls = search pages for each site
        search_pages = {
                        "amazon" : "http://www.amazon.com/s/ref=nb_sb_noss?url=search-alias%3Daps&field-keywords=" + search_query, \
                        "amazoncouk" : "http://www.amazon.co.uk/s/ref=nb_sb_noss?url=search-alias%3Daps&field-keywords=" + search_query, \
                        "walmart" : "http://www.walmart.com/search/search-ng.do?ic=16_0&Find=Find&search_query=%s&Find=Find&search_constraint=0" % search_query, \
                        "bloomingdales" : "http://www1.bloomingdales.com/shop/search?keyword=%s" % search_query, \
                        "overstock" : "http://www.overstock.com/search?keywords=%s" % search_query, \
                        "wayfair" : "http://www.wayfair.com/keyword.php?keyword=%s" % search_query, \
                        "bestbuy" : "http://www.bestbuy.com/site/searchpage.jsp?_dyncharset=ISO-8859-1&_dynSessConf=-26268873911681169&id=pcat17071&type=page&st=%s&sc=Global&cp=1&nrp=15&sp=&qp=&list=n&iht=y&fs=saas&usc=All+Categories&ks=960&saas=saas" % search_query, \
                        "toysrus": "http://www.toysrus.com/search/index.jsp?kw=%s" % search_query, \
                        "ebay": "http://www.ebay.com/sch/i.html?_trksid=p2050601.m570.l1313&_nkw=%s" % search_query, \
                        "ebaycouk": "http://www.ebay.co.uk/sch/i.html?_trksid=p2050601.m570.l1313&_nkw=%s" % search_query, \
                        "sony": "http://store.sony.com/search?SearchTerm=%s" % search_query, \
                        "samsung": "http://www.samsung.com/us/function/search/espsearchResult.do?input_keyword=%s" % search_query, \
                        "target" : "http://www.target.com/s?searchTerm=" + search_query + "&category=0%7CAll%7Cmatchallpartial%7Call+categories&lnk=snav_sbox_" + search_query, \
                        "ocado" : "http://www.ocado.com/webshop/getSearchProducts.do?clearTabs=yes&isFreshSearch=true&entry=%s" % search_query,
                        "tesco" : "http://www.tesco.com/direct/search-results/results.page?catId=4294967294&searchquery=%s" % search_query,
                        "boots" : "http://www.boots.com/webapp/wcs/stores/servlet/EndecaSearchListerView?storeId=10052&searchTerm=%s" % search_query,
                        "currys" : "http://www.currys.co.uk/gbuk/search-keywords/xx_xx_xx_xx_xx/%s/xx-criteria.html" % search_query,
                        "pcworld" : "http://www.pcworld.co.uk/gbuk/search-keywords/xx_xx_xx_xx_xx/%s/xx-criteria.html" % search_query,
                        "maplin" : "http://www.maplin.co.uk/search?text=%s" % search_query, \
                        "argos" : "http://www.argos.co.uk/static/Search/searchTerm/%s.htm" % search_query, \
                        "ebuyer" : "http://www.ebuyer.com/search?q=%s" % search_query, \
                        "firebox" : "http://www.firebox.com/firebox/search?searchstring=%s" % search_query, \
                        "rakuten" : "http://www.rakuten.co.uk/search/%s/" % search_query, \
                        "rscomponents" : "http://uk.rs-online.com/web/c/?searchTerm=%s" % search_query, \
                        "screwfix" : "http://www.screwfix.com/search?search=%s" % search_query, \
                        "macys" : "http://www1.macys.com/shop/search?keyword=%s" % search_query, \
                        "kohls": "http://www.kohls.com/search.jsp?search=%s" % search_query
                        }

        return search_pages

    def build_search_query(self, product_name):
        # put + instead of spaces, lowercase all words
        search_query = "+".join(ProcessText.normalize(product_name, stem=False, exclude_stopwords=False))
        return search_query

    def parse_bestsellers_range(self, bestsellers_range_string):
        '''Parse input string bestsellers range into a tuple of integers
        representing the range of bestsellers to extract for this spider
        :param bestsellers_range_string: bestsellers range as string of the form
        [x-y] or 0
        '''

        if bestsellers_range_string == '0':
            return []
        else:
            return map(lambda x: int(x), bestsellers_range_string.split("-"))

    def parse_products_file(self, products_file):
        '''Parse input csv containing the needed columns for the source product,
        instead of using the input url and scraping for them
        '''
        products = []
        with open(products_file) as f:

                reader = csv.DictReader(f, delimiter=',', quoting=csv.QUOTE_MINIMAL)
                
                while True:
                    try:
                        data = next(reader)
                        product = {}
                        try:
                            product['origin_name'] = data['Product_Name']
                        except Exception:
                            self.log("No product name in csv for row " + str(data) + "\n", level=log.INFO)
                        try:
                            product['origin_upc'] = data['UPC']
                        except Exception:
                            self.log("No UPC in csv for row " + str(data) + "\n", level=log.INFO)
                        try:
                            product['product_origin_price'] = float(data['product_origin_price'])
                        except Exception:
                            # exclude currency
                            try:
                                product['product_origin_price'] = float(data['product_origin_price'][1:])
                            except Exception:
                                pass
                        try:
                            product['origin_model'] = data['Product_Model']
                            product['origin_asin'] = data['ASIN']
                            product['origin_brand'] = data['Brand']
                            product['origin_url'] = data['URL']
                        except Exception:
                            pass
                        products.append(product)
                    except StopIteration, e:
                        break

        return products

    # def send_search_queries(self, product_upc, product_model, product_brand, product_name, product_url, product_price, product_brand_extracted, product_manufacturer_code, origin_manufacturer_code=None):
    def send_search_queries(self, origin_product):
        '''Build search queries from product features, return a request with pending requests in its meta,
        with all search queries to be done
        '''

        # recieve requests for search pages with queries as:
        # 1) product upc (if available)
        # 2) product model (if available)
        # 3) product name
        # 4) parts of product's name
        # 
        
        # generate id for current input product
        product_identifier = uuid.uuid4().hex

        request = None
        pending_requests = []

        # 1) Search by UPC
        if 'origin_upc' in origin_product and origin_product['origin_upc']:
            query0 = self.build_search_query(origin_product['origin_upc'])
            search_pages0 = self.build_search_pages(query0)
            #page1 = search_pages1[self.target_site]
            page0 = search_pages0[self.target_site]

            request0 = Request(page0, callback = self.parseResults)

            request0.meta['query'] = query0
            request0.meta['target_site'] = self.target_site
            request0.meta['origin_product_id'] = product_identifier            
            
            if not request:
                request = request0
            else:
                pending_requests.append(request0)

        

        # 2) Search by model number
        if 'origin_model' in origin_product and origin_product['origin_model']:

            #TODO: model was extracted with ProcessText.extract_model_from_name(), without lowercasing, should I lowercase before adding it to query?
            query1 = self.build_search_query(origin_product['origin_model'])
            search_pages1 = self.build_search_pages(query1)
            page1 = search_pages1[self.target_site]

            request1 = Request(page1, callback = self.parseResults)

            request1.meta['query'] = query1
            request1.meta['target_site'] = self.target_site
            request1.meta['origin_product_id'] = product_identifier
            
            if not request:
                request = request1
            else:
                pending_requests.append(request1)

        # 3) Search by model number + brand/first word
        if 'origin_model' in origin_product and origin_product['origin_model']:

            #TODO: model was extracted with ProcessText.extract_model_from_name(), without lowercasing, should I lowercase before adding it to query?
            query2 = None
            if 'origin_brand' in origin_product and origin_product['origin_brand'] :
                query2 = self.build_search_query(origin_product['origin_model'] + " " + origin_product['origin_brand'])
            else:
                if 'origin_name' in origin_product and origin_product['origin_name']:
                    query2 = self.build_search_query(origin_product['origin_model'] + " " + ProcessText.normalize(origin_product['origin_name'])[0])
            if query2:
                search_pages2 = self.build_search_pages(query2)
                page2 = search_pages2[self.target_site]

                request2 = Request(page2, callback = self.parseResults)

                request2.meta['query'] = query2
                request2.meta['target_site'] = self.target_site
                request2.meta['origin_product_id'] = product_identifier
            
                if not request:
                    request = request2
                else:
                    pending_requests.append(request2)


        # 4) Search by product full name
        if 'origin_name' in origin_product and origin_product['origin_name']:
            query3 = self.build_search_query(origin_product['origin_name'])
            search_pages3 = self.build_search_pages(query3)
            #page2 = search_pages2[self.target_site]
            page3 = search_pages3[self.target_site]
            request3 = Request(page3, callback = self.parseResults)

            request3.meta['query'] = query3
            request3.meta['target_site'] = self.target_site
            request3.meta['origin_product_id'] = product_identifier

            if not request:
                request = request3
            else:
                pending_requests.append(request3)

            # 5) Search by combinations of words in product's name
            # create queries

            for words in ProcessText.words_combinations(origin_product['origin_name'], fast=self.fast):
                query4 = self.build_search_query(" ".join(words))
                search_pages4 = self.build_search_pages(query4)
                #page3 = search_pages3[self.target_site]
                page4 = search_pages4[self.target_site]
                request4 = Request(page4, callback = self.parseResults)

                request4.meta['query'] = query4
                request4.meta['target_site'] = self.target_site
                request4.meta['origin_product_id'] = product_identifier

                pending_requests.append(request4)

        request.meta['pending_requests'] = pending_requests

        self.results[product_identifier] = {
        'origin_product': origin_product,
        'search_requests': {
            r.meta['query']:\
             {'search_results': [], 'product_items': []}
            for r in [request] + pending_requests
            }
        }

        return request


    # parse input and build list of URLs to find matches for, send them to parseURL
    def parse(self, response):

        # log spider version - will match commit number of last change
        self.log("Spider version: " + self.version + "\n", level=log.INFO)

        if self.product_name:

            # can inly use this option if self.target_site has been initialized (usually true for spiders for retailers sites, not true for manufacturer's sites)
            if not self.target_site:
                self.log("You can't use the product_name option without setting the target site to search on\n", level=log.ERROR)
                raise CloseSpider("\nYou can't use the product_name option without setting the target site to search on\n")

            search_query = self.build_search_query(self.product_name)
            search_pages = self.build_search_pages(search_query)

            request = Request(search_pages[self.target_site], callback = self.parseResults)

            request.meta['origin_name'] = self.product_name
            request.meta['query'] = search_query

            # just use empty product model and url, for compatibility, also pending_requests
            request.meta['origin_model']  = ''
            request.meta['origin_url'] = ''
            request.meta['pending_requests'] = []

            yield request

        if self.products_file:
            # TODO: is this necessary?
            if not self.target_site:
                self.log("You can't use the product_name option without setting the target site to search on\n", level=log.ERROR)
                raise CloseSpider("\nYou can't use the product_name option without setting the target site to search on\n")

            products_info = self.parse_products_file(self.products_file)
            for product_info in products_info:
            
                origin_product = product_info
                if 'origin_model' not in origin_product:
                    origin_product['origin_model'] = ProcessText.extract_model_from_url(product_url)
                

                # TODO: find another way soon
                for attribute in ('origin_name', 'origin_model', 'product_origin_price', \
                    'origin_upc', 'origin_manufacturer_code'):
                    if attribute not in origin_product or not origin_product[attribute]:
                        origin_product[attribute] = ""

            yield self.send_search_queries(origin_product)

        if self.bestsellers_link:
            origin_site = Utils.extract_domain(self.bestsellers_link)
            yield Request(self.bestsellers_link, callback=self.parse_bestsellers_functions[origin_site])

        # if we have product URLs, pass them to parseURL to extract product names (which will pass them to parseResults)
        product_urls = []
        # if we have a single product URL, create a list of URLs containing it
        if self.product_url:
            product_urls.append(self.product_url)

        # if we have a file with a list of URLs, create a list with URLs found there
        if self.product_urls_file:
            f = open(self.product_urls_file, "r")
            for line in f:
                product_urls.append(line.strip())
            f.close()

        for product_url in product_urls:
            origin_site = Utils.extract_domain(product_url)
            
            request = Request(product_url, callback = self.parseURL)
            request.meta['origin_site'] = origin_site
            if origin_site == 'staples':
                zipcode = "12345"
                request.cookies = {"zipcode": zipcode}
                request.meta['dont_redirect'] = True
            yield request

    def parse_bestsellers_amazon(self, response):
        '''Parse input bestsellers link to extract all bestseller products,
        and pass them over to parseURL to start matching with these as
        origin urls
        '''
        # e.g.
        # http://www.amazon.com/Best-Sellers-Electronics-Televisions/zgbs/electronics/172659/ref=zg_bs_nav_e_2_1266092011

        hxs = HtmlXPathSelector(response)
        product_links = hxs.select("//div[@class='zg_title']/a/@href").extract()

        if 'last_index' not in response.meta:
            last_index = 0
        else:
            last_index = response.meta['last_index']

        # index of product in bestsellers lists
        index = last_index

        for product_link in product_links:
            # start matching for this product
            index = index + 1
            # only consider products in the range given as input
            if self.bestsellers_range and self.bestsellers_range[0] <= index < self.bestsellers_range[1]:
                yield Request(product_link.strip(), callback=self.parseURL, meta={'origin_site' : 'amazon', 'origin_bestsellers_rank' : index})
            pass

        # go to next page
        # if we're already past the index range, skip further pages
        if not self.bestsellers_range or index <= self.bestsellers_range[1]:
            try:
                next_page_link = hxs.select("//ol[@class='zg_pagination']/li[@class='zg_page zg_selected']/following-sibling::li[1]/a/@href")\
                .extract()[0]
                yield Request(next_page_link, callback=self.parse_bestsellers_amazon, meta={'last_index' : index})
            except Exception, e:
                pass

    def parse_bestsellers_walmart(self, response):
        '''Parse input bestsellers link to extract all bestseller products,
        and pass them over to parseURL to start matching with these as
        origin urls
        '''
        # e.g.
        # http://www.walmart.com/browse/electronics/tvs/3944_1060825_447913

        hxs = HtmlXPathSelector(response)
        product_links = hxs.select("//div[@class='js-tile tile-grid-unit']/a[@class='js-product-title']/@href").extract()

        if 'last_index' not in response.meta:
            last_index = 0
        else:
            last_index = response.meta['last_index']
        index = last_index

        for product_link in product_links:
            # start matching for this product
            product_link = "http://www.walmart.com" + product_link.strip()
            index = index + 1
            
            # only consider products in the range given as input
            if self.bestsellers_range and self.bestsellers_range[0] <= index < self.bestsellers_range[1]:
                yield Request(product_link, callback=self.parseURL, meta={'origin_site' : 'walmart', 'origin_bestsellers_rank' : index})

        # go to next page
        # if we're already past the index range, skip further pages
        if not self.bestsellers_range or index <= self.bestsellers_range[1]:
            try:
                next_page_link = hxs.select("//a[@class='paginator-btn paginator-btn-next']/@href").extract()[0]
                base_url = urllib.splitquery(response.url)[0]
                next_page_link = base_url + next_page_link
                yield Request(next_page_link, callback=self.parse_bestsellers_walmart, meta={'last_index' : index})
            except Exception, e:
                pass


    # parse a product page (given its URL) and extract product's name;
    # create queries to search by (use model name, model number, and combinations of words from model name), then send them to parseResults
    def parseURL(self, response):

        site = response.meta['origin_site']
        hxs = HtmlXPathSelector(response)

        #############################################################
        # Extract product attributes (differently depending on site)
        if site in self.parse_url_functions:
            origin_product = self.parse_url_functions[site](hxs)
        else:
            raise CloseSpider("Unsupported site: " + site)
        origin_product['origin_url'] = response.url

        for attribute in ('origin_name', 'origin_model', 'product_origin_price', \
            'origin_upc', 'origin_manufacturer_code'):
            if attribute not in origin_product or not origin_product[attribute]:
                origin_product[attribute] = ""
        #
        # Log errors and return empty matches if no name was found
        #
        # if no product name, abort and send the item like it is (no match)
        if not origin_product['origin_name']:
            sys.stderr.write("Broken product page link (can't find item title): " + response.url + "\n")
            # return the item as a non-matched item
            item = SearchItem()
            item['origin_url'] = response.url
            item['origin_name'] = ''

            #TODO: move this somewhere more relevant
            # remove unnecessary parameters for walmart links
            m = re.match("(.*)\?enlargedSearch.*", item['origin_url'])
            if m:
                item['origin_url'] = m.group(1)


            if self.name != 'manufacturer':
                # don't return empty matches in manufacturer spider
                yield item
            return

        # for walmart price extraction is implemented, so warn if it's not found
        if not origin_product['product_origin_price'] and site=='walmart':
            self.log("Didn't find product price: " + response.url + "\n", level=log.DEBUG)

        if site == 'staples':
            zipcode = "12345"
            cookies = {"zipcode": zipcode}
        else:
            cookies = {}


        #######################################################################
        # Create search queries to the second site, based on product attributes

        request = None

        #TODO: search by alternative model numbers?

        #TODO: search by model number extracted from product name? Don't I do that implicitly? no, but in combinations

        # if there is no product model, try to extract it
        if not origin_product['origin_model'] and origin_product['origin_name']:
            origin_product['origin_model'] = ProcessText.extract_model_from_name(origin_product['origin_name'])

            if not origin_product['origin_model']:
                origin_product['origin_model'] = ProcessText.extract_model_from_url(response.url)

        product_name_tokenized = [word.lower() for word in origin_product['origin_name'].split(" ")]
        #TODO: maybe extract brand as word after 'by', if 'by' is somewhere in the product name
        if len(product_name_tokenized) > 0 and re.match("[a-z]*", product_name_tokenized[0]):
            product_brand_extracted = product_name_tokenized[0].lower()

        # if we are in manufacturer spider, set target_site to manufacturer site

        # for manufacturer spider set target_site of request to brand extracted from name for this particular product
        if self.name == 'manufacturer':

            #TODO: restore commented code; if brand not found, try to search for it on every manufacturer site (build queries fo every supported site)
            self.target_site = product_brand_extracted

            # can only go on if site is supported
            # (use dummy query)
            if product_brand_extracted not in self.build_search_pages("").keys():

                product_brands_extracted = set(self.build_search_pages("").keys()).intersection(set(product_name_tokenized))
                
                if product_brands_extracted:
                    product_brand_extracted = product_brands_extracted.pop()
                    #target_site = product_brand_extracted
                else:
                    # give up and return item without match
                    self.log("Manufacturer site not supported (" + product_brand_extracted + ") or not able to extract brand from product name (" + product_name + ")\n", level=log.ERROR)

                    ## comment lines below to: don't return anything if you can't search on manufacturer site
                    # item = SearchItem()
                    # item['origin_url'] = response.url
                    # item['origin_name'] = product_name
                    # if product_model:
                    #     item['origin_model'] = product_model
                    # yield item
                    return

            # if specific site is not set, search on manufacturer site as extracted from name
            if not self.manufacturer_site:
                target_site = product_brand_extracted
            else:
                # if it's set, continue only if it matches extracted brand
                if self.manufacturer_site!= product_brand_extracted:
                    self.log("Will abort matching for product, extracted brand does not match specified manufacturer option (" + product_brand_extracted + ")\n", level=log.INFO)

                    ## comment lines below to: don't return anything if you can't search on manufacturer site
                    # item = SearchItem()
                    # item['origin_url'] = response.url
                    # item['origin_name'] = product_name
                    # if product_model:
                    #     item['origin_model'] = product_model
                    # yield item
                    return

                else:
                    target_site = product_brand_extracted
                    # # try to match it without specific site (manufacturer spider will try to search on all manufacturer sites)
                    # target_site = None



        # for other (site specific) spiders, set target_site of request to class variable self.target_site set in class "constructor" (init_sub)
        else:
            target_site = self.target_site

        if 'origin_bestsellers_rank' in response.meta:
            origin_bestsellers_rank = response.meta['origin_bestsellers_rank']
        else:
            origin_bestsellers_rank = None

        pending_requests = []

        yield self.send_search_queries(origin_product)


    ####################
    # Site-specific parseURL functions - for extracting attributes origin products (to be matched)
    # return dictionary with product features, their names the same as the fields in SearchItem

    def parseURL_staples(self, hxs):

        product_name = hxs.select("//h1/text()").extract()[0]

        model_nodes = hxs.select("//p[@class='itemModel']/text()").extract()

        product_model = None
        if model_nodes:
            model_node = model_nodes[0]

            model_node = re.sub("\W", " ", model_node, re.UNICODE)
            m = re.match("(.*)Model:(.*)", model_node.encode("utf-8"), re.UNICODE)
            
            
            if m:
                product_model = m.group(2).strip()

        product = {}
        product['origin_name'] = product_name
        product['origin_model'] = product_model


    def parseURL_walmart(self, hxs):

        product_name_holder = hxs.select("//h1[contains(@class, 'product-name')]//text()").extract()

        # try for old page version
        if not product_name_holder:
            product_name_holder = hxs.select("//h1[@class='productTitle']//text()").extract()

        if product_name_holder:
            product_name = "".join(product_name_holder).strip()
        else:
            product_name = None

        product_price_node = hxs.select("//meta[@itemprop='price']/@content").extract()
        # remove currency and , (e.g. 1,000)
        if product_price_node:
            product_price = float(re.sub("[\$,]", "", product_price_node[0]))
        else:
            product_price = None

        # # Not relevant anymore:
        # # TODO: figure out what this list of prices contained
        # # get integer part of product price
        # try for old page version

        if not product_price_node:
            product_price_big = hxs.select("//span[@class='bigPriceText1']/text()").extract()

            # if there is a range of prices take their average
            if len(product_price_big) > 1:

                # remove $ and .
                product_price_min = re.sub("[\$\.,]", "", product_price_big[0])
                product_price_max = re.sub("[\$\.,]", "", product_price_big[-1])

                #TODO: check if they're ints?
                product_price_big = (int(product_price_min) + int(product_price_max))/2.0

            elif product_price_big:
                product_price_big = int(re.sub("[\$\.,]", "", product_price_big[0]))

            # get fractional part of price
            #TODO - not that important

            if product_price_big:
                product_price = product_price_big
            else:
                product_price = None


        product_model_holder = hxs.select("//div[@class='specs-table']/table//td[contains(text(),'Model')]/following-sibling::*/text()").extract()

        # try for old page version
        if not product_model_holder:
            product_model_holder = hxs.select("//td[contains(text(),'Model')]/following-sibling::*/text()").extract()

        if product_model_holder:
            product_model = product_model_holder[0].strip()
        else:
            product_model = None

        upc = None
        product_upc_holder = hxs.select("//meta[@itemprop='productID']/@content").extract()
        if product_upc_holder:
            upc = product_upc_holder[0].strip()

        brand_holder = hxs.select("//meta[@itemprop='brand']/@content | //span[@itemprop='brand']/text()").extract()
        if brand_holder:
            product_brand = brand_holder[0]
        else:
            product_brand = None

        try:
            product_category_tree = hxs.select("//li[@class='breadcrumb']/a/span[@itemprop='name']/text()").extract()[1:]
        except:
            product_category_tree = None

        try:
            keywords = hxs.select("//meta[@name='keywords']/@content").extract()[0]
        except:
            keywords = None


        product = {}
        product['origin_name'] = product_name
        product['origin_model'] = product_model
        product['product_origin_price'] = product_price
        product['origin_upc'] = upc
        product['origin_brand'] = product_brand
        product['origin_category_tree'] = product_category_tree
        product['origin_keywords'] = keywords
        return product

    def parseURL_wayfair(self, hxs):

        product_name_holder = hxs.select("//span[@class='title_name']/text()").extract()

        if product_name_holder:
            product_name = product_name_holder[0].strip()
        else:
            product_name = None

        product_price_node = hxs.select("//span[contains(@class,'product_origin_price')]//text()").extract()
        product_price_raw = "".join(product_price_node)
        # remove currency and , (e.g. 1,000)
        if product_price_node:
            product_price = float(re.sub("[\$,]", "", product_price_raw))
        else:
            product_price = None

        brand_holder = hxs.select("//span[@class='manu_name']/a/text()").extract()
        if brand_holder:
            product_brand = brand_holder[0].strip()
        else:
            product_brand = None

        product = {}
        product['origin_name'] = product_name
        product['product_origin_price'] = product_price
        product['origin_brand'] = product_brand
        return product        

#TODO: for the sites below, complete with missing logic, for not returning empty elements in manufacturer spider
    def parseURL_newegg(self, hxs):

        product_name_holder = hxs.select("//span[@itemprop='name']/text()").extract()
        if product_name_holder:
            product_name = product_name_holder[0].strip()
        else:
            product_name = None

        # else:
        #     sys.stderr.write("Broken product page link (can't find item title): " + response.url + "\n")
        #     item = SearchItem()
        #     #item['origin_site'] = site
        #     item['origin_url'] = response.url
        #     yield item
        #     return
        product_model_holder = hxs.select("//dt[text()='Model']/following-sibling::*/text()").extract()
        if product_model_holder:
            product_model = product_model_holder[0]
        else:
            product_model = None

        product = {}
        product['origin_name'] = product_name
        product['origin_model'] = product_model
        return product

    #TODO: add price info? product model? brand?
    def parseURL_boots(self, hxs):
        product_name_holder = hxs.select("//div[@class='pd_productName']/h2/span[@itemprop='name']/text()").extract()

        if product_name_holder:
            product_name = product_name_holder[0]
        else:
            product_name = None

        product = {}
        product['origin_name'] = product_name
        return product

    #TODO: add price info? product model? brand?
    def parseURL_ocado(self, hxs):
        # extract all text in this node, including product name and quantity and concatenate it to one string
        product_name = " ".join(map(lambda x: x.strip(), hxs.select("//h1[@class='productTitle']//text()").extract()))
        # if it's the empty string, set it to None
        if not product_name:
            product_name = None

        product = {}
        product['origin_name'] = product_name
        return product

    #TODO: add price info? product model? brand
    def parseURL_tesco(self, hxs):
        product_name_holder = hxs.select("//h1[@class='page-title']/text()").extract()

        if product_name_holder:
            product_name = product_name_holder[0].strip()
        else:
            product_name_holder = None

        product = {}
        product['origin_name'] = product_name
        return product

    def parseURL_amazon(self, hxs):
        # works for amazon.com and amazon.co.uk
        # no implementation for amazon.co.uk for: category tree, keywords
        product_name = product_model = price = None

        product_name_node = hxs.select('//h1[@id="title"]/span[@id="productTitle"]/text()').extract()
        if not product_name_node:
            product_name_node = hxs.select('//h1[@id="aiv-content-title"]//text()').extract()
        if not product_name_node:
            product_name_node = hxs.select('//div[@id="title_feature_div"]/h1//text()').extract()

        if product_name_node:
            product_name = product_name_node[0].strip()
        else:
            # needs special treatment
            product_name_node = hxs.select('//h1[@class="parseasinTitle " or @class="parseasinTitle"]/span[@id="btAsinTitle"]//text()').extract()
            if product_name_node:
                product_name = " ".join(product_name_node).strip()

        # extract product model number
        model_number_holder = hxs.select("""//tr[@class='item-model-number']/td[@class='value']/text() |
         //li/b/text()[normalize-space()='Item model number:']/parent::node()/parent::node()/text()""").extract()
        if model_number_holder:
            model_number = model_number_holder[0].strip()
        # if no product model explicitly on the page, try to extract it from name
        else:
            # TODO: do I try this here or is it tried somewhere down the line again?
            if product_name:
                product_model_extracted = ProcessText.extract_model_from_name(product_name)
                if product_model_extracted:
                    model_number = product_model_extracted

        brand_holder = hxs.select("//div[@id='brandByline_feature_div']//a/text() | //a[@id='brand']/text()").extract()
        if brand_holder:
            brand = brand_holder[0]
        else:
            brand = None
            #sys.stderr.write("Didn't find product brand: " + response.url + "\n")

        # extract price
        #! extracting list price and not discount price when discounts available?
        # TODO: test. it extracts more than one price
        price_holder = hxs.select("//span[contains(@id,'priceblock')]/text() | //span[@class='a-color-price']/text() " + \
            "| //span[@class='listprice']/text() | //span[@id='actualPriceValue']/text() | //b[@class='priceLarge']/text() | //span[@class='price']/text()").extract()

        # if we can't find it like above try other things:
        if not price_holder:
            # prefer new prices to used ones
            price_holder = hxs.select("//span[contains(@class, 'olp-new')]//text()[contains(.,'$')]").extract()
        if price_holder:
            product_target_price = price_holder[0].strip()
            # remove commas separating orders of magnitude (ex 2,000)
            product_target_price = re.sub(",","",product_target_price)
            m = re.match("(\$|\xa3)([0-9]+\.?[0-9]*)", product_target_price)
            if m:
                price = float(m.group(2))
                currency = m.group(1)
                if currency != "$":
                    price = Utils.convert_to_dollars(price, currency)
            else:
                self.log("Didn't match product price: " + product_target_price + " (" + str(product_name) + ")\n", level=log.WARNING)

        else:
            self.log("Didn't find product price: (" + str(product_name) + ")\n", level=log.INFO)

        try:
            product_category_tree = \
            filter(None, map(lambda c: c.strip(), hxs.select("//ul[li[@class='a-breadcrumb-divider']]/li/span[@class='a-list-item']/a/text()").extract()))
        except Exception, e:
            product_category_tree = None

        try:
            keywords = hxs.select("//meta[@name='keywords']/@content").extract()[0]
        except:
            keywords = None

        try:
            product_image = hxs.select("//img[@id='landingImage']/@src").extract()[0]
        except:
            product_image = None

        product = {}
        product['origin_name'] = product_name
        product['origin_model'] = product_model
        product['product_origin_price'] = price
        product['origin_image_url'] = product_image
        product['origin_image_encoded'] = ProcessText.encode_image(product_image)
        # TODO
        # product['origin_upc'] = upc
        product['origin_brand'] = brand
        product['origin_category_tree'] = product_category_tree
        product['origin_keywords'] = keywords
        return product

    def parseURL_target(self, hxs):
        product_name_holder = hxs.select("//h2[@class='product-name item']/span[@itemprop='name']/text()").extract()

        if product_name_holder:
            product_name = product_name_holder[0].strip()
        else:
            product_name = None

        price_holder = hxs.select("//span[@class='offerPrice']/text()").extract()

        price = None
        if price_holder:
            product_target_price = price_holder[0].strip()
            # remove commas separating orders of magnitude (ex 2,000)
            product_target_price = re.sub(",","",product_target_price)
            m = re.match("\$([0-9]+\.?[0-9]*)", product_target_price)
            if m:
                price = float(m.group(1))
            else:
                sys.stderr.write("Didn't match product price: " + product_target_price + "\n")

        # as source site, we are only interested in the UPC, not the DPCI.
        # We won't be searching on other sites by DPCI.
        upc = None

        upc_node = hxs.select("//meta[@property='og:upc']/@content").extract()
        if upc_node:
            upc = upc_node[0]

        product = {}
        product['origin_name'] = product_name
        product['product_origin_price'] = price
        product['origin_upc'] = upc
        return product

    def parseURL_maplin(self, hxs):
        product_name_holder = hxs.select("//h1[@itemprop='name']/text()").extract()

        if product_name_holder:
            product_name = product_name_holder[0].strip()
        else:
            product_name = None

        price_holder = hxs.select("//meta[@itemprop='price']/@content").extract()

        price = None
        if price_holder:
            product_target_price = price_holder[0].strip()
            if product_target_price:
                # remove commas separating orders of magnitude (ex 2,000)
                product_target_price = re.sub(",","",product_target_price)
                price = float(product_target_price)

                try:
                    currency = hxs.select("//meta[@itemprop='priceCurrency']/@content").extract()[0].strip()
                    if currency == 'GBP':
                        # convert to dollars
                        price = Utils.convert_to_dollars(price, u'\xa3')
                except Exception, e:
                    self.log("Error extracting currency: " + str(e), level=log.DEBUG)

        upc = None

        try:
            product_code = hxs.select("//span[@itemprop='sku']/text()").extract()[0]
        except Exception:
            self.log("No code for product " + str(product_name), level=log.WARNING)
            product_code = None

        product = {}
        product['origin_name'] = product_name
        product['product_origin_price'] = price
        product['origin_upc'] = upc
        product['origin_manufacturer_code'] = product_code
        return product

    # accumulate results for each (sending the pending requests and the partial results as metadata),
    # and lastly select the best result by selecting the best match between the original product's name and the result products' names
    def reduceResults(self, response):

        #TODO: do we still need this?
        if 'parsed' not in response.meta:

            # pass to specific prase results function (in derived class)
            return self.parseResults(response)

        else:
            del response.meta['parsed']


        origin_product_id = response.meta['origin_product_id']

        # all product urls from all queries
        # TODO: is this right??
        items = sum(map(lambda q: self.results[origin_product_id]['search_requests'][q]['product_items'], \
            self.results[origin_product_id]['search_requests']), [])

        ## print stuff
        origin_product = self.results[response.meta['origin_product_id']]['origin_product']
        self.log_product_features(origin_product)
        self.log( "QUERY: " + response.meta['query'], level=log.DEBUG)
        self.log( "MATCHES: ", level=log.DEBUG)
        for item in items:
            try:
                self.log( item['product_name'].decode("utf-8"), level=log.DEBUG)
            except UnicodeEncodeError, e:
                self.log( item['product_name'], level=log.DEBUG)
        self.log( '\n', level=log.DEBUG)


        # if there is a pending request (current request used product model, and pending request is to use product name),
        # continue with that one and send current results to it as metadata
        if 'pending_requests' in response.meta:
            # yield first request in queue and send the other ones as metadata
            pending_requests = response.meta['pending_requests']

            if pending_requests:
                # print "PENDING REQUESTS FOR", response.meta['origin_url'], response.meta['origin_name']
                request = pending_requests[0]

                # update pending requests
                request.meta['pending_requests'] = pending_requests[1:]

                return request

            # if there are no more pending requests, use cumulated items to find best match and send it as a result
            else:
                best_match = None

                if items:
                    # from all results, select the product whose name is most similar with the original product's name
                    # if there was a specific threshold set in request, use that, otherwise, use the class variable
                    try:
                        threshold = response.meta['threshold']
                    except:
                        threshold = self.threshold

                    best_match = ProcessText.similar(items, threshold)

                self.log( "FINAL: " + str(best_match), level=log.WARNING)
                self.log( "\n----------------------------------------------\n", level=log.WARNING)

                if not best_match:
                    # if there are no results but the option was to include original product URL, create an item with just that
                    # output item if match not found for either output type
                    item = SearchItem()
                    for field in origin_product:
                        item[field] = origin_product[field]

                    return [item]

                return best_match

        else:
            # output item if match not found
            item = SearchItem()
            
            for field in origin_product:
                item[field] = origin_product[field]

            self.log( "FINAL: " + str(item), level=log.WARNING)
            self.log( "\n----------------------------------------------\n", level=log.WARNING)

            return [item]

    def extract_walmart_id(self, url):
        m = re.match(".*/ip/([0-9]+)", url)
        if m:
            return m.group(1)

    def remove_result_from_queue(self, uuid, url):
        '''Remove search result from self.results
        '''
        # TODO: find more efficient way
        for q in self.results[uuid]['search_requests']:
            self.results[uuid]['search_requests'][q]['search_results'] = \
                filter(lambda u: u!=url, self.results[uuid]['search_requests'][q]['search_results'])

    def log_product_features(self, product):
        for key in ('origin_name', 'origin_model', 'origin_upc', 'origin_manufacturer_code', 'origin_brand', 'origin_category_tree'):
            if key not in product or not product[key]:
                product[key] = ''

        self.log("PRODUCT: " + product['origin_name'].decode("utf-8") + " MODEL: " + product['origin_model'].decode("utf-8") +\
         " UPC: " + str(product['origin_upc']).decode("utf-8") + " MANUFACTURER_CODE: " + product['origin_manufacturer_code'].decode("utf-8") + \
         " BRAND: " + product['origin_brand'].decode("utf-8") + " CATEGORIES: " + str(product['origin_category_tree']), level=log.DEBUG)
