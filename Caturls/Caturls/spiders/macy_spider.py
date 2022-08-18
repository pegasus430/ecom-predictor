from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from scrapy.http import TextResponse
from Caturls.items import ProductItem
from Caturls.spiders.caturls_spider import CaturlsSpider
from pprint import pprint
from scrapy import log

from spiders_utils import Utils

import re
import sys
import json

################################
# Run with 
#
# scrapy crawl macy -a cat_page="<url>" [-a outfile="<filename>"]
#
################################


class MacySpider(CaturlsSpider):

    name = "macy"
    allowed_domains = ["macys.com"]

        # macy's sneakers
        #self.start_urls = ["http://www1.macys.com/shop/shoes/sneakers?id=26499&edge=hybrid"]
        # macy's blenders
        #self.start_urls = ["http://www1.macys.com/shop/kitchen/blenders?id=46710&edge=hybrid"]
        # macy's coffee makers
        #self.start_urls = ["http://www1.macys.com/shop/kitchen/coffee-makers?id=24733&edge=hybrid"]
        # macy's mixers

    def parse(self, response):
            hxs = HtmlXPathSelector(response)

            m = re.match("http://www1.macys.com/shop(.*)\?id=([0-9]+).*", self.cat_page)
            cat_id = 0
            if m:
                cat_id = int(m.group(2))
            productids_request = "http://www1.macys.com/catalog/category/facetedmeta?edge=hybrid&categoryId=%d&pageIndex=1&sortBy=ORIGINAL&productsPerPage=40&" % cat_id
            return Request(productids_request, callback = self.parseCategory, headers = {"Cookie" : "shippingCountry=US"}, meta={'dont_merge_cookies': True, "cat_id" : cat_id, "page_nr" : 1})


    # parse macy's category
    def parseCategory(self, response):

        json_response = json.loads(unicode(response.body, errors='replace'))
        product_ids = json_response['productIds']

        # if there are any product ids parse them and go to the next page
        # (if there are no product ids it means the current page is empty and we stop)
        if product_ids:
            cat_id = response.meta['cat_id']

            product_ids2 = [str(cat_id) + "_" + str(product_id) for product_id in product_ids]
            product_ids_string = ",".join(product_ids2)

            products_page = "http://www1.macys.com/shop/catalog/product/thumbnail/1?edge=hybrid&limit=none&suppressColorSwatches=false&categoryId=%d&ids=%s" % (cat_id, product_ids_string)
            # parse products from this page
            request = Request(products_page, callback = self.parsePage, headers = {"Cookie" : "shippingCountry=US"}, meta={'dont_merge_cookies': True, "cat_id" : cat_id})
            yield request

            # send a new request for the next page
            page = int(response.meta['page_nr']) + 1
            next_page = re.sub("pageIndex=[0-9]+", "pageIndex=" + str(page), response.url)
            request = Request(next_page, callback = self.parseCategory, headers = {"Cookie" : "shippingCountry=US"}, meta={'dont_merge_cookies': True, "cat_id" : cat_id, "page_nr" : page})
            yield request

    # parse macy's page and extract product URLs
    def parsePage(self, response):
        hxs = HtmlXPathSelector(response)

        products = hxs.select("//div[@class='shortDescription']/a")

        items = []
        root_url = "http://www1.macys.com"
        for product in products:
            item = ProductItem()
            item['product_url'] = root_url + product.select("@href").extract()[0]
            items.append(item)

        return items
