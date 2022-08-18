from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from scrapy.http import TextResponse
from Caturls.items import ProductItem
from pprint import pprint
from scrapy import log

from selenium import webdriver
from selenium.webdriver.common.keys import Keys

from spiders_utils import Utils

import time
import re
import sys
import json



################################
# 
#
# Abstract spider class
#
################################


# search for a product in all sites, using their search functions; give product as argument by its name or its page url
class CaturlsSpider(BaseSpider):

    name = "producturls"
    allowed_domains = ["staples.com", "bloomingdales.com", "walmart.com", "amazon.com", "bestbuy.com", \
    "nordstrom.com", "macys.com", "williams-sonoma.com", "overstock.com", "newegg.com", "tigerdirect.com"]

    # store the cateory page url given as an argument into a field and add it to the start_urls list
    def __init__(self, cat_page, outfile = "product_urls.txt", with_categories = False, use_proxy = False):
        self.cat_page = cat_page
        self.start_urls = [cat_page]
        self.outfile = outfile
        self.use_proxy = use_proxy

        # flag to classify products by category, with additional 'cat' column in the output csv
        self.with_categories = with_categories

        # keep track of parsed pages to avoid duplicates
        # used for newegg motherboards
        self.parsed_pages = []


    # Functions for brand filtering - currently supported by spiders: boots, ocado, tesco
    
    # create normalized verions of a brand name to fuzzy match against - include fill brands, also split by words etc
    def brand_versions_fuzzy(self, brand):
        retval = []

        # eliminate these words from brands words lists. their matching would not be relevant
        exceptions = ['and', 'solutions', 'food', 'hair', 'simple']

        brand = brand.lower()

        # split by spaces and non-words
        tokens = re.split("[^\w]+", brand)

        # add tokens to final list, if they have > 2 letters (eliminate 's', or 'st')
        retval += filter(lambda x: len(x)>2, tokens)

        # add whole brand name with words concatenated to final list
        concatenated = re.sub("[^\w]", "", brand)
        retval.append(concatenated)

        # remove exceptions from list
        retval = filter(lambda x: x not in exceptions, retval)

        return list(set(retval))


    # determine if a brand name is among the filter brand names; use fuzzy matching
    #TODO: this has problems such as matching 2 brands that contain common words, like 'solutions'. currently avoiding this by hardcoded exceptions list in brand_versions_fuzzy
    def name_matches_brands(self, name):
        name_versions = self.brand_versions_fuzzy(name)
        common = set(name_versions).intersection(set(self.brands_normalized))

        # return True if common is not empty
        return not not common
