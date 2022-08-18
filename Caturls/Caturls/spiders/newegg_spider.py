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
# scrapy crawl newegg -a cat_page="<url>" [-a outfile="<filename>"]
#
################################


class NeweggSpider(CaturlsSpider):

    name = "newegg"
    allowed_domains = ["newegg.com"]

    # newegg laptops
    #self.start_urls = ["http://www.newegg.com/Laptops-Notebooks/SubCategory/ID-32"]
    # newegg videocards http://www.newegg.com/Video-Cards-Video-Devices/Category/ID-38
    # newegg motherboards http://www.newegg.com/Motherboards/Category/ID-20
    # newegg cameras http://www.newegg.com/DSLR-Cameras/SubCategory/ID-784

    def parse(self, response):
        return Request(url = self.cat_page, callback = self.parsePage, meta = {'page' : 1})


    def parsePage(self, response):
        hxs = HtmlXPathSelector(response)

        if response.url in self.parsed_pages:
            return
        else:
            self.parsed_pages.append(response.url)

        product_links = hxs.select("//div[@class='itemText']/div[@class='wrapper']/a")

        # if you don't find any product links, try to crawl subcategories in left menu,
        # but only the ones under the first part of the menu
        # do this by selecting all dd elements in the menu until a dt (another title) element is found
        if not product_links:
            # select first element in menu
            el = hxs.select("//dl[@class='categoryList primaryNav']//dd[1]")

            # while we still find another subcategory in the menu before the next title
            while el:
                # parse the link as a subcategory
                subcat_url = el.select("a/@href").extract()[0]
                # clean URL of parameters. 
                # if this is not done, it will end up in a infinite loop below (constructing next pages urls, they will always point to the same page, first one)
                m = re.match("([^\?]+)\?.*", subcat_url)
                if m:
                    subcat_url = m.group(1)
                yield Request(url = subcat_url, callback = self.parsePage, meta = {'page' : 1})

                # get next element in menu (that is not a title)
                el = el.select("following-sibling::*[1][self::dd]")

        else:

            for product_link in product_links:
                item = ProductItem()
                item['product_url'] = product_link.select("@href").extract()[0]
                yield item

            # crawl further pages - artificially construct page names by changing parameter in URL
            # only try if there is a "next" link on the page, pointing to the next page, so as not to be stuck in an infinite loop

            next_page = hxs.select("//li[@class='enabled']/a[@title='next']")
            if next_page:
                page = int(response.meta['page']) + 1
                next_url = ""
                if page == 2:
                    next_url = response.url + "/Page-2"
                else:
                    m = re.match("(http://www.newegg.com/.*Page-)[0-9]+", response.url)
                    if m:
                        next_url = m.group(1) + str(page)

                    else:
                        self.log("Error: not ok url " + response.url + " , page " + str(page), level=log.WARNING)
                        return

                yield Request(url = next_url, callback = self.parsePage, meta = {'page' : page})
                #print 'next url ', next_url