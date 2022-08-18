from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from Categories.items import CategoryItem
from Categories.items import ProductItem
from scrapy.http import Request
from scrapy.http import TextResponse
from selenium import webdriver
import re
import datetime
import time
import sys

################################
# Run with 
#
# scrapy crawl bloomingdales
#
################################

# scrape sitemap list and retrieve categories
class BloomingdalesSpider(BaseSpider):
    name = "bloomingdales"
    allowed_domains = ["bloomingdales.com"]
    start_urls = [
        "http://www1.bloomingdales.com/service/sitemap/index.ognc?cm_sp=NAVIGATION-_-BOTTOM_LINKS-_-SITE_MAP",
    ]

    def __init__(self, outfile=None):

        self.outfile = outfile

        # keep crawled items represented by (url, parent_url, level) tuples
        # to eliminate duplicates
        self.crawled = []

        # level that is considered to contain departments
        self.DEPARTMENT_LEVEL = 1


    def parse(self, response):
        hxs = HtmlXPathSelector(response)
        links = hxs.select("//div[@class='sr_siteMap_container']/div[position()>2 and position()<5]//a")
        root_url = "http://www1.bloomingdales.com"

        #TODO: add registry as special category?

        department_id = 0

        for link in links:
            item = CategoryItem()
            item['text'] = link.select('text()').extract()[0]
            url = link.select('@href').extract()[0]
            # if it's a relative URL complete it with the domain
            if not url.startswith("http"):
                url = root_url + url

            item['url'] = url
            item['level'] = 1

            department_id += 1

            item['department_text'] = item['text']
            item['department_url'] = item['url']
            item['department_id'] = department_id

            #yield item

            # create request to extract subcategories for this category
            yield Request(item['url'], callback = self.parseCategory, meta = {'parent' : item, \
                "department_text" : item['text'], "department_url" : item['url'], "department_id" : department_id, \
                "dont_merge_cookies" : True}, \
                cookies = {"shippingCountry" : "US"}, headers = {"Cookie" : "shippingCountry=" + "US"})

    # extract subcategories from each category
    def parseCategory(self, response):
        hxs = HtmlXPathSelector(response)
        parent = response.meta['parent']

        # extract product count if any
        product_count_holder = hxs.select("//span[@class='productCount'][1]/text()").extract()
        if product_count_holder:
            parent['nr_products'] = int(product_count_holder[0])

        # extract description if any
        # just assume no description (haven't found any page with descriptions for bloomingdales)
        parent['description_wc'] = 0

        # yield parent item (if it hasn't been output before)
        if 'parent_url' not in parent or (parent['url'], parent['parent_url'], parent['level']) not in self.crawled:
            if 'parent_url' in parent:
                self.crawled.append((parent['url'], parent['parent_url'], parent['level']))
            yield parent

        # extract subcategories
        subcats = hxs.select("//div[@class='gn_left_nav2_standard']//a")
        for subcat in subcats:
            item = CategoryItem()
            item['text'] = subcat.select('text()').extract()[0]
            item['url'] = subcat.select('@href').extract()[0]
            item['level'] = parent['level'] - 1
            item['parent_text'] = response.meta['parent']['text']
            item['parent_url'] = response.url
            item['department_text'] = response.meta['department_text']
            item['department_url'] = response.meta['department_url']
            item['department_id'] = response.meta['department_id']

            # create request to extract subcategories for this category
            yield Request(item['url'], callback = self.parseCategory, meta = {'parent' : item, \
                "department_text" : item['department_text'], "department_url" : item['department_url'], "department_id" : item['department_id'], \
                "dont_merge_cookies" : True}, \
                cookies = {"shippingCountry" : "US"}, headers = {"Cookie" : "shippingCountry=" + "US"})



################################
# Run with 
#
# scrapy crawl bestseller
#
################################

# scrape bestsellers list and retrieve products
class BestsellersSpider(BaseSpider):
    name = "bloomingdales_bestseller"
    allowed_domains = ["bloomingdales.com"]
    start_urls = [
        "http://www1.bloomingdales.com/service/sitemap/index.ognc?cm_sp=NAVIGATION-_-BOTTOM_LINKS-_-SITE_MAP",
    ]

    def parse(self, response):

        # list of bestsellers pages
        pages = [
                    # handbags
                "http://www1.bloomingdales.com/shop/handbags/best-sellers?id=23173",\
                    # shoes
                "http://www1.bloomingdales.com/shop/shoes/best-sellers?id=23268", \
                ]

        # call parsePage for each of these pages
        for page_i in range(len(pages)):
            request = Request(pages[page_i], callback = self.parseDept)
            if page_i == 0:
                department = "Handbags"
            else:
                department = "Shoes"
            #print "+++++++++++++++++" + pages[page_i]
            request.meta['department'] = department
            yield request

    def parseDept(self, response):
        department = response.meta['department']
        
        items = []

        ## set up proxy
        # PROXY_HOST = "64.71.156.216"
        # PROXY_PORT = "8181"
        # fp = webdriver.FirefoxProfile()
        # # Direct = 0, Manual = 1, PAC = 2, AUTODETECT = 4, SYSTEM = 5
        # fp.set_preference("network.proxy.type", 1)

        # fp.set_preference("network.proxy.http", PROXY_HOST)
        # fp.set_preference("network.proxy.http_port", PROXY_PORT)

        # driver = webdriver.Firefox(firefox_profile=fp)

        # use selenium to select the sorting option
        driver = webdriver.Firefox()
        driver.get(response.url)

        # use selenium to select USD currency
       
        link = driver.find_element_by_xpath("//li[@id='bl_nav_account_flag']//a")
        link.click()
        time.sleep(5)
        button = driver.find_element_by_id("iShip_shipToUS")
        button.click()
        time.sleep(10)

        dropdown = driver.find_element_by_id("sortBy")
        for option in dropdown.find_elements_by_tag_name("option"):
            if option.text == 'Best Sellers':
                option.click()

        time.sleep(5)


        # convert html to "nice format"
        text_html = driver.page_source.encode('utf-8')
        html_str = str(text_html)

        # this is a hack that initiates a "TextResponse" object (taken from the Scrapy module)
        resp_for_scrapy = TextResponse('none',200,{},html_str,[],None)
       
        # pass first page to parsePage function to extract products
        items += self.parsePage(resp_for_scrapy, department)

        hxs = HtmlXPathSelector(resp_for_scrapy)


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
            items += self.parsePage(resp_for_scrapy, department)

            hxs = HtmlXPathSelector(resp_for_scrapy)
            next_page_url = hxs.select("//li[@class='nextArrow']//a")

        driver.close()

        return items

    def parsePage(self, response, department):
        hxs = HtmlXPathSelector(response)
        products = hxs.select("//div[@class='productThumbnail showQuickView']")

        if not products:
            return
        
        # counter to hold rank of product
        rank = 0

        for product in products:
            item = ProductItem()

            rank += 1
            item['rank'] = str(rank)

            # get item department from response's meta
            item['department'] = department

            # extract name and url from bestsellers list
            product_link = product.select("div[@class='shortDescription']/a")
            name = product_link.select("text()").extract()
            if name:
                item['list_name'] = name[0]
            url = product_link.select("@href").extract()
            if url:
                item['url'] = url[0]

            # if there's no url move on to next product
            else:
                continue

            #TODO: add net price?

            # price = product.select(".//div[@class='prices']//span[@class='priceBig']/text()").extract()
            # if price:
            #     item['price'] = price[0]

            # call parseProduct method on each product]
            request = Request(item['url'], callback = self.parseProduct)
            request.meta['item'] = item

            yield request

    def parseProduct(self, response):

        #TODO: add date
        hxs = HtmlXPathSelector(response)
        product_name = hxs.select("//h1[@id='productTitle']/text()").extract()[0]

        page_title = hxs.select("//title/text()").extract()[0]

        item = response.meta['item']

        # remove page suffix " | Bloomingdales"
        m = re.match("(.*) \| Bloomingdale's", page_title, re.UNICODE)
        if m:
            page_title = m.group(1).strip()

        item['page_title'] = page_title
        item['product_name'] = product_name

        price = hxs.select("//span[@class='priceBig']/text()").extract()
        if price:
            item['price'] = price[0]

        # add date
        item['date'] = datetime.date.today().isoformat()

        return item
