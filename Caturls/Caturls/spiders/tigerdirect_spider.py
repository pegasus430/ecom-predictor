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
# scrapy crawl tigerdirect -a cat_page="<url>" [-a outfile="<filename>"]
#
################################


class TigerdirectSpider(CaturlsSpider):

    name = "tigerdirect"
    allowed_domains = ["tigerdirect.com"]

    # tigerdirect DSLR cameras
    #self.start_urls = ["http://www.tigerdirect.com/applications/Category/guidedSearch.asp?CatId=7&sel=Detail;131_1337_58001_58001"]

    def parse(self, response):
        return Request(url = self.cat_page, callback = self.parsePage,\
            # add as meta the page number and the base URL to which to append page number if necessary
         meta = {'page' : 1, 'base_url' : self.cat_page})


    # parse a Tigerdirect category page and extract product URLs
    def parsePage(self, response):
        hxs = HtmlXPathSelector(response)
        #print "IN PARSEPAGE ", response.url

        # without the "resultsWrap" div, these are found on pages we don't want as well
        product_links = hxs.select("//div[@class='resultsWrap listView']//h3[@class='itemName']/a/@href").extract()
        for product_link in product_links:
            item = ProductItem()
            item['product_url'] = Utils.add_domain(product_link, "http://www.tigerdirect.com")
            # remove CatId from URL (generates duplicates)
            m = re.match("(.*)&CatId=[0-9]+", item['product_url'])
            if m:
                item['product_url'] = m.group(1)
            yield item

        # parse next pages (if results spread on more than 1 page)
        #TODO: not sure if all of them are extracted
        next_page = hxs.select("//a[@title='Next page']")
        if next_page:
            #print "next page : ", response.url, " + ", next_page
            page_nr = response.meta['page'] + 1
            # base_url = response.meta['base_url']
            # # remove trailing "&" character at the end of the URL
            # m = re.match("(.*)&", base_url)
            # if m:
            #     base_url = m.group(1)
            # yield Request(url = base_url + "&page=%d"%page_nr, callback = self.parsePage,\
            #      meta = {'page' : page_nr, 'base_url' : response.meta['base_url']})
            next_page_url = Utils.add_domain(next_page.select("@href").extract()[0], "http://www.tigerdirect.com")
            yield Request(url = next_page_url, callback = self.parsePage,\
                meta = {'page' : page_nr})


        # if you can't find product links, you should search for links to the subcategories pages and parse them for product links
        if not product_links:
            yield Request(url = response.url, callback = self.parseSubcats)


    # parse a Tigerdirect category page and extract its subcategories to pass to the page parser (parsePage)
    def parseSubcats(self, response):
        hxs = HtmlXPathSelector(response)

        # search for a link to "See All Products"
        seeall = hxs.select("//span[text()='See All Products']/parent::node()/@href").extract()
        if seeall:
            # pass the new page to this same method to be handled by the next branch of the if statement
            yield Request(url = Utils.add_domain(seeall[0], "http://www.tigerdirect.com"), callback = self.parseSubcats)
        else:
            # extract subcategories
            subcats_links = hxs.select("//div[@class='sideNav']/div[@class='innerWrap'][1]//ul/li/a")
            for subcat_link in subcats_links:
                subcat_url = Utils.add_domain(subcat_link.select("@href").extract()[0], "http://www.tigerdirect.com")
                yield Request(url = subcat_url, callback = self.parsePage,\
                 meta = {'page' : 1, 'base_url' : subcat_url})