from scrapy.contrib.httpcache import DummyPolicy
from scrapy.selector import HtmlXPathSelector
import sys

import os
import cPickle as pickle
from time import time
from weakref import WeakKeyDictionary
from email.utils import mktime_tz, parsedate_tz
from w3lib.http import headers_raw_to_dict, headers_dict_to_raw
from scrapy.http import Headers
from scrapy.responsetypes import responsetypes
from scrapy.utils.request import request_fingerprint
from scrapy.utils.project import data_path
from scrapy.utils.httpobj import urlparse_cached

class SamsungCachePolicy(DummyPolicy):
 def should_cache_response(self, response, request):

     sys.stderr.write("IN CACHE POLICY")
     print "RESPONSE", response
     #print isinstance(response.body_as_unicode(), unicode)
     print type(response)

     # if response:
     #     hxs = HtmlXPathSelector(response)

     #     # if we can't find the desired element on a search results page, don't cache it
     #     title = hxs.select("//title/text()").extract()[0]
     #     desired_element = hxs.select("//input[contains(@id,'detailpageurl')]/@value")
     #     if title == "SEARCH SAMSUNG" and not desired_element:
     #         sys.stderr.write("TITLE WAS " + title)
     #         return False
     #     else:
     #         sys.stderr.write("TITLE WAS NOT SEARCH BUT " + title)

     return response.status not in self.ignore_http_codes