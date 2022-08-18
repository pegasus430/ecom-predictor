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
# scrapy crawl bloomingdales -a cat_page="<url>" [-a outfile="<filename>"]
#
################################


class BloomingdalesSpider(CaturlsSpider):

    name = "bloomingdales"
    allowed_domains = ["bloomingdales.com"]

    # bloomingdales sneakers
    #self.start_urls = ["http://www1.bloomingdales.com/shop/shoes/sneakers?id=17400"]

    def parse(self, response):

        items = []

        driver = webdriver.Firefox()
        driver.get(response.url)
        
        # use selenium to select USD currency
        link = driver.find_element_by_xpath("//li[@id='bl_nav_account_flag']//a")
        link.click()
        time.sleep(5)
        button = driver.find_element_by_id("iShip_shipToUS")
        button.click()
        time.sleep(10)

        # convert html to "nice format"
        text_html = driver.page_source.encode('utf-8')
        html_str = str(text_html)

        # this is a hack that initiates a "TextResponse" object (taken from the Scrapy module)
        resp_for_scrapy = TextResponse('none',200,{},html_str,[],None)

        # parse first page with parsePage function
        items += self.parsePage(resp_for_scrapy)
        hxs = HtmlXPathSelector(resp_for_scrapy)

        # while there is a next page get it and pass it to parsePage
        next_page_url = hxs.select("//li[@class='nextArrow']//a")
        
        while next_page_url:

        # use selenium to click on next page arrow and retrieve the resulted page if any
            next = driver.find_element_by_xpath("//li[@class='nextArrow']//a")
            next.click()

            time.sleep(5)

            # convert html to "nice format"
            text_html = driver.page_source.encode('utf-8')
            html_str = str(text_html)

            # this is a hack that initiates a "TextResponse" object (taken from the Scrapy module)
            resp_for_scrapy = TextResponse('none',200,{},html_str,[],None)

            # pass the page to parsePage function to extract products
            items += self.parsePage(resp_for_scrapy)

            hxs = HtmlXPathSelector(resp_for_scrapy)
            next_page_url = hxs.select("//li[@class='nextArrow']//a")

        driver.close()

        return items


    # parse bloomingdales page and extract product URLs
    def parsePage(self, response):
        hxs = HtmlXPathSelector(response)
        items = []
        products = hxs.select("//div[@class='shortDescription']")
        for product in products:
            item = ProductItem()
            item['product_url'] = product.select("a/@href").extract()[0]
            items.append(item)
        return items

