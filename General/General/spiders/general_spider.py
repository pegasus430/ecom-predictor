from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from General.items import CategoryItem
from General.items import ProductItem
from scrapy.http import Request
import sys
import re
import datetime

from spiders_utils import Utils


################################
# Run with 
#
# scrapy crawl products -a prod_pages_file="<urls_file>" [-a outfile="<filename>"]
#
################################

# scrape product page and extract info on it
class ProductsSpider(BaseSpider):
    name = "products"
    allowed_domains = ["walmart.com", "bestbuy.com", "newegg.com", "tigerdirect.com", "overstock.com", "bloomingdales.com", "macys.com",\
    "amazon.com", "staples.com", "williams-sonoma.com"] # to be added - check bitbucket
    start_urls = [
        # random url, will not be used
        "http://www.walmart.com",
    ]

    # store the cateory page url given as an argument into a field and add it to the start_urls list
    def __init__(self, prod_pages_file, outfile = "product_urls.txt", use_proxy = False):
        self.prod_pages_file = prod_pages_file
        self.outfile = outfile
        urlsfile = open(prod_pages_file, "r")
        self.prod_urls = []
        for line in urlsfile:
            self.prod_urls.append(line.strip())
        urlsfile.close()

    def parse(self, response):
        for url in self.prod_urls:
            domain =  Utils.extract_domain(url)
            #TODO: pass some cookie with country value for sites where price for example is displayed in local currency
            if domain != 'staples':
                yield Request(url, callback = self.parseProdpage, meta = {"site" : domain})
            # for staples we need extra cookies
            else:
                yield Request(url, callback = self.parseProdpage, cookies = {"zipcode" : "1234"}, \
            headers = {"Cookie" : "zipcode=" + "1234"}, meta = {"dont_redirect" : True, "dont_merge_cookies" : True, "site" : domain})

    def parseProdpage(self, response):
        hxs = HtmlXPathSelector(response)

        item = ProductItem()
        item['url'] = response.url
        item['site'] = response.meta['site']

        product_name = self.extractProdname(hxs)
        if product_name:
            item['product_name'] = product_name

        product_price = self.extractProdprice(selector=hxs, item=item)
        if product_price:
            item['price'] = product_price

        yield item


    # given a selector for a product's page, extract and return the product's name
    def extractProdname(self, selector):
        #########################
        # Product title:
        # Works for:
        #
        #   macys
        #   amazon              //span[@id='btAsinTitle']/text(), //h1[@id='title']/text(), //h1[@class='parseasinTitle, //h1[@class='parseasintitle']/text()
        #   bloomingdales       //h1[@id='productTitle']/text()
        #   overstock           //h1/text()
        #   newegg              //h1/span[@itemprop='name']/text()
        #   tigerdirect
        #   walmart             //h1[@class='productTitle']/text()
        #   bestbuy             //hi[@itemprop='name']/text()
        #
        # Doesn't work for:
        #   staples - a few exceptions
        #
        #############################
        # Price:
        # Works for:
        #
        #
        #
        #
        #


        # select tags with "Title", then with "title" in their class or id
        # if none, select h1 tags, if there is only one assume that's the title
        # if more than one?
        # if none?
        # eliminate ones with just whitespace
        #TODO: idea: check similarity with page title
        #TODO: idea - also look into text, see which is more belivable
        product_name_holder = selector.select("//h1[contains(@id, 'Title') or contains(@class, 'Title')]//text()[normalize-space()!='']")
        product_name = None
        # if there are more than 2, exclude them, it can't be right
        if product_name_holder and len(product_name_holder) < 2:
            # select ones that don't only contain whitespace
            product_name = product_name_holder.extract()[0].strip()
        else:
            # find which sites need this
            #product_name_holder = selector.select("//*[contains(@id, 'Title') or contains(@class, 'Title')]//text()[normalize-space()!='']")
            if product_name_holder and len(product_name_holder) < 2:
                product_name = product_name_holder.extract()[0].strip()
            else:
                product_name_holder = selector.select("//h1[contains(@*, 'title') or contains(@*, 'Title') or contains (@*, 'name')]//text()[normalize-space()!='']")
                if product_name_holder and len(product_name_holder) < 2:
                    product_name = product_name_holder.extract()[0].strip()
                else:
                    product_name_holder = selector.select("//*[contains(@*, 'Title') or contains(@*,'title')]//text()[normalize-space()!='']")
                    if product_name_holder and len(product_name_holder) < 2:
                        product_name = product_name_holder.extract()[0].strip()
                    else:
                        h1s = selector.select("//h1//text()[normalize-space()!='']")
                        if len(h1s) == 1:
                            product_name = h1s.extract()[0].strip()
                        else:
                            print 'Error: no product name: ', response.url

        # normalize spaces in product name
        if product_name:
            product_name = re.sub("\s+", " ", product_name)


         # # bestbuy
        # item['product_name'] = selector.select("//h1/text()").extract()[0].strip()

        # # overstock
        # product_name = selector.select("//h1/text()").extract()[0]

        # # bloomingdales
        # product_name = selector.select("//h1[@id='productTitle']/text()").extract()[0]

        # # macys


        return product_name

    # given a selector for a product's page, extract and return the product's price
    #TODO: using item argument only for testing
    def extractProdprice(self, item, selector):

        #TODO: needs improvement
        # maybe write some rule to exclude prices that are not in a normal range. somehow...look at neighboring products, look at category name?
        # extract price

        #TODO
        # go progressively up until you think you've captured the entire price
        #price_holder = selector.select("//*[contains(text(), '$') or contains(text(), 'USD') or contains(text(), 'usd')]/parent::*/parent::*")
        #price_holder = selector.select("//*[(contains(text(), '$') or contains(text(), 'USD') or contains(text(), 'usd')) and (contains(@*, 'Price') or contains(@*, 'price'))]")
        price_holder = selector.select("//*[not(self::script or self::style) and contains(text(), '$') or contains(text(), 'USD') or contains(text(), 'usd')]")
        # look for number regular expressions - accept anything that could occur in a price string, in case it's all inside one tag (.,$ etc)
        #TODO: also test if it contains either: usd, USD, $, number
        price = price_holder.select(".//text()[string-length()<20 or (string-length()<20 and contains(.,'price'))]").re("[0-9\s\.,$USDusd]+")
        # assume first value is dollars and second is cents (if they are different)
        if len(price) > 1 and price[0] != price[1]:
            #TODO: errors for tigerdirect when price is > 1000 => 1.999
            price_string = "$" + price[0] + "." + price[1]
        else:
            if price:
                price_string = "$" + price[0]


            #TODO: what if there are more prices on the page, like for other products? see tigerdirect
            # with css, get largest element on the page?
            # for now try to get all prices on the page. then focus on filtering only the right one

        print "\n*******************\n", item['site'], item['url'], '\n', "\n--------------------------------\n".join(\
            map(lambda x: Utils.prettify_html(x),[s if type(s) is str else s.encode("utf-8", errors="ignore") \
                for s in price_holder.select("parent::*").extract()]))
        
        if price:
            return price_string

        return None