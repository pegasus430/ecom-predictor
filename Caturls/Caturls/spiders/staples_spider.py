from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from scrapy.http import TextResponse
from Caturls.items import ProductItem
from Caturls.spiders.caturls_spider import CaturlsSpider
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
# Run with 
#
# scrapy crawl staples -a cat_page="<url>" [-a outfile="<filename>"]
#
################################


class StaplesSpider(CaturlsSpider):

    name = "staples"
    allowed_domains = ["staples.com"]

    # staples televisions
    #self.start_urls = ["http://www.staples.com/Televisions/cat_CL142471"]

    def parse(self, response):

        ############################################
        #
        # # Use selenium - not necessary anymore


        # # zipcode = "12345"

        # # hxs = HtmlXPathSelector(response)
        # # return Request(self.cat_page, callback = self.parsePage, cookies = {"zipcode" : zipcode}, meta = {"dont_redirect" : False})
        # # use selenium to complete the zipcode form and get the first results page
        # driver = webdriver.Firefox()
        # driver.get(response.url)

        # # set a hardcoded value for zipcode
        # zipcode = "12345"
        # textbox = driver.find_element_by_name("zipCode")

        # if textbox.is_displayed():
        #     textbox.send_keys(zipcode)

        #     button = driver.find_element_by_id("submitLink")
        #     button.click()

        #     cookie = {"zipcode": zipcode}
        #     driver.add_cookie(cookie)

        #     time.sleep(5)

        # # convert html to "nice format"
        # text_html = driver.page_source.encode('utf-8')
        # #print "TEXT_HTML", text_html
        # html_str = str(text_html)

        # # this is a hack that initiates a "TextResponse" object (taken from the Scrapy module)
        # resp_for_scrapy = TextResponse('none',200,{},html_str,[],None)
        # #resp_for_scrapy = TextResponse(html_str)

        # # pass first page to parsePage function to extract products
        # items += self.parsePage(resp_for_scrapy)

        # # use selenium to get next page, while there is a next page
        # next_page = driver.find_element_by_xpath("//li[@class='pageNext']/a")
        # while (next_page):
        #     next_page.click()
        #     time.sleep(5)

        #     # convert html to "nice format"
        #     text_html = driver.page_source.encode('utf-8')
        #     #print "TEXT_HTML", text_html
        #     html_str = str(text_html)

        #     # this is a hack that initiates a "TextResponse" object (taken from the Scrapy module)
        #     resp_for_scrapy = TextResponse('none',200,{},html_str,[],None)
        #     #resp_for_scrapy = TextResponse(html_str)

        #     # pass first page to parsePage function to extract products
        #     items += self.parsePage(resp_for_scrapy)

        #     hxs = HtmlXPathSelector(resp_for_scrapy)
        #     next = hxs.select("//li[@class='pageNext']/a")
        #     next_page = None
        #     if next:
        #         next_page = driver.find_element_by_xpath("//li[@class='pageNext']/a")

        #     #TODO: this doesn't work
        #     # try:
        #     #     next_page = driver.find_element_by_xpath("//li[@class='pageNext']/a")
        #     #     break
        #     # except NoSuchElementException:
        #     #     # if there are no more pages exit the loop
        #     #     driver.close()
        #     #     return items

        # driver.close()

        # return items
        #
        ##############################################

        zipcode = "12345"
        request = Request(response.url, callback = self.parsePage, cookies = {"zipcode" : zipcode}, \
            headers = {"Cookie" : "zipcode=" + zipcode}, meta = {"dont_redirect" : True, "dont_merge_cookies" : True})
        return request

    # parse staples page and extract product URLs
    def parsePage(self, response):

        hxs = HtmlXPathSelector(response)

        #print 'title parsepage ', hxs.select("//h1/text()").extract()

        products = hxs.select("//a[@class='url']")
        root_url = "http://www.staples.com"

        for product in products:

            item = ProductItem()
            item['product_url'] = root_url + product.select("@href").extract()[0]
            yield item

        #yield items

        nextPage = hxs.select("//li[@class='pageNext']/a/@href").extract()
        zipcode = "12345"
        if nextPage:
            # parse next page, (first convert url from unicode to string)
            yield Request(str(nextPage[0]), callback = self.parsePage, cookies = {"zipcode" : zipcode}, \
                headers = {"Cookie" : "zipcode=" + zipcode}, meta = {"dont_redirect" : True, "dont_merge_cookies" : True})


