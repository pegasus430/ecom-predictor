from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from scrapy.http import TextResponse
from Categories.items import CategoryItem

from selenium import webdriver
from selenium.webdriver.common.keys import Keys

from spiders_utils import Utils

import time
import re

################################
# Run with 
#
# scrapy crawl staples
#
################################


# search for a product in all sites, using their search functions; give product as argument by its name or its page url
class StaplesSpider(BaseSpider):

    name = "staples"
    allowed_domains = ["staples.com"]
    # use one random category page as the root page to extract departments
    start_urls = ["http://www.staples.com/Televisions/cat_CL142471"]

    def __init__(self, outfile=None):
        self.outfile = outfile

        # level that is considered to contain departments
        self.DEPARTMENT_LEVEL = 1



    def parse(self, response):

        
        # # use selenium to complete the zipcode form and get the first results page
        # driver = webdriver.Firefox()
        # driver.get(response.url)

        # # set a hardcoded value for zipcode
        # zipcode = "12345"

        # textbox = driver.find_element_by_name("zipCode")
        # textbox.send_keys(zipcode)

        # button = driver.find_element_by_id("submitLink")
        # button.click()

        # cookie = {"zipcode": zipcode}
        # driver.add_cookie(cookie)

        # time.sleep(5)

        # # convert html to "nice format"
        # text_html = driver.page_source.encode('utf-8')
        # #print "TEXT_HTML", text_html
        # html_str = str(text_html)

        # # this is a hack that initiates a "TextResponse" object (taken from the Scrapy module)
        # resp_for_scrapy = TextResponse('none',200,{},html_str,[],None)

        # driver.close()

        # # parse department list
        # items = self.parseList(resp_for_scrapy)

        # return items

        zipcode = "12345"
        request = Request(response.url, callback = self.parseList, cookies = {"zipcode" : zipcode}, \
            headers = {"Cookie" : "zipcode=" + zipcode}, meta = {"dont_redirect" : True, "dont_merge_cookies" : True})
        return request

    def parseList(self, response):
        hxs = HtmlXPathSelector(response)
        
        items = []
        # add all department names
        departments = hxs.select("//div[@id='showallprods']/ul/li/a")

        root_url = "http://www.staples.com"

        department_id = 0

        for department in departments:
            item = CategoryItem()

            item['text'] = department.select("text()").extract()[0]
            item['url'] = root_url + department.select("@href").extract()[0]
            item['level'] = 1

            #yield item

            # # parse each department page for its categories, pass the department item too so that it's added to the list in parseDept
            # yield Request(item['url'], callback = self.parseDept, meta = {"department": item})

            department_id += 1

            zipcode = "12345"
            request = Request(item['url'], callback = self.parseDept, cookies = {"zipcode" : zipcode}, \
                headers = {"Cookie" : "zipcode=" + zipcode}, meta = {"dont_redirect" : True, "dont_merge_cookies" : True, \
                "parent": item, "level": 1, \
                "department_text" : item["text"], "department_url" : item["url"], "department_id" : department_id})
            yield request


    def parseDept(self, response):

        # for "copy & print" there's an exception, we don't need zipcode

        # # use selenium to complete the zipcode form and get the first results page
        # driver = webdriver.Firefox()
        # driver.get(response.url)

        # # set a hardcoded value for zipcode
        # zipcode = "12345"

        # textbox = driver.find_element_by_name("zipCode")
        # textbox.send_keys(zipcode)

        # button = driver.find_element_by_id("submitLink")
        # button.click()

        # cookie = {"zipcode": zipcode}
        # driver.add_cookie(cookie)

        # time.sleep(5)

        # # convert html to "nice format"
        # text_html = driver.page_source.encode('utf-8')
        # #print "TEXT_HTML", text_html
        # html_str = str(text_html)

        # # this is a hack that initiates a "TextResponse" object (taken from the Scrapy module)
        # resp_for_scrapy = TextResponse('none',200,{},html_str,[],None)


        # hxs = HtmlXPathSelector(resp_for_scrapy)


        #TODO: doesn't extract Televisions for ex

        hxs = HtmlXPathSelector(response)
        categories = hxs.select("//h2/a")

        root_url = "http://www.staples.com"

        # from parent's page:
        item = response.meta['parent']

        # add department name, url and id to item
        item['department_text'] = response.meta['department_text']
        item['department_url'] = response.meta['department_url']
        item['department_id'] = response.meta['department_id']

        # extract number of items, if any
        nritems_holder = hxs.select("//div[@class='perpage']/span[@class='note']/text()").extract()
        if nritems_holder:
            m = re.findall("[0-9]+\s*items", nritems_holder[0])
            if m:
                item['nr_products'] = int("".join(re.findall("[0-9]+", m[0])))
            # else:
            #     print "NOT MATCH ", nritems_holder[0]

        # extract description, if any
        description_texts = hxs.select("//h2[@class='seo short']//text() | //h2[@class='seo short long']//text()").extract()
        if description_texts and reduce(lambda x,y: x or y, [line.strip() for line in description_texts]):
            # replace all whitespace with one space, strip, and remove empty texts; then join them
            item['description_text'] = " ".join([re.sub("\s+"," ", description_text.strip()) for description_text in description_texts if description_text.strip()])

            if item['description_text']:
                item['description_title'] = item['text']

                tokenized = Utils.normalize_text(item['description_text'])
                item['description_wc'] = len(tokenized)

                (item['keyword_count'], item['keyword_density']) = Utils.phrases_freq(item['description_title'], item['description_text'])

            else:
                # if no description is found
                #print 'desc_holder but no desc_text ', response.URL
                item['description_wc'] = 0
        else:
            item['description_wc'] = 0

        # yield item the request came from (parent)
        yield item


        # extract subcategories
        for category in categories:
            # there are pages that don't have categories
            item = CategoryItem()
            text = category.select("text()").extract()
            if text:
                item['text'] = text[0]
            url = category.select("@href").extract()
            if url:
                item['url'] = root_url + url[0]
            item['level'] = int(response.meta['level']-1)
            if 'text' in response.meta['parent']:
                item['parent_text'] = response.meta['parent']['text']
            else:
                print 'no text in parent ', response.meta['parent']
            item['parent_url'] = response.url

            # yield the item after passing it through request and collecting additonal info
            #yield item

            # extract subcategories if any
            zipcode = "12345"
            request = Request(item['url'], callback = self.parseDept, cookies = {"zipcode" : zipcode}, \
                headers = {"Cookie" : "zipcode=" + zipcode}, meta = {"dont_redirect" : True, "dont_merge_cookies" : True, \
                "parent": item, "level": item['level'], \
                "department_text" : response.meta["department_text"], "department_url" : response.meta["department_url"], "department_id" : response.meta["department_id"]})
            yield request

