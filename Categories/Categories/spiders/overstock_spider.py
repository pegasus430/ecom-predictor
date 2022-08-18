from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from Categories.items import CategoryItem
from Categories.items import ProductItem
from scrapy.http import Request
import sys
import re
import datetime

################################
# Run with 
#
# scrapy crawl overstock
#
################################

# scrape sitemap and extract categories
class OverstockSpider(BaseSpider):
    name = "overstock"
    allowed_domains = ["overstock.com"]
    start_urls = [
        "http://www.overstock.com/sitemap",
    ]

    def __init__(self, outfile=None):
        self.outfile = outfile

        # level that is considered to contain departments
        self.DEPARTMENT_LEVEL = 1


    def parse(self, response):
        hxs = HtmlXPathSelector(response)
        # currently selecting bottom level categories, and their parents and parents of parents ("grandparents") in their fields
        links = hxs.select("//div[@id='sitemap']//li[@class='bullet3']//a")
        parent_links = hxs.select("//div[@id='sitemap']//li[@class='bullet2']//a")
        grandparent_links = hxs.select("//div[@id='sitemap']//li[@class='bullet1']//a")
        items = []

        #TODO: mark special categories (if appropriate for any)

        for link in links:

            # extract immediate parent of this link (first preceding sibling (of the parent node) with class='bullet2')
            parent = link.select("parent::node()/preceding-sibling::*[@class='bullet2'][1]/a")
            # extract grandparent of this link (first preceding sibling of the parent's parent node witch class='bullet1')
            grandparent = parent.select("parent::node()/preceding-sibling::*[@class='bullet1'][1]/a")

            item = CategoryItem()
            item['text'] = link.select('text()').extract()[0]
            item['url'] = link.select('@href').extract()[0]

            item['parent_text'] = parent.select('text()').extract()[0]
            item['parent_url'] = parent.select('@href').extract()[0]

            item['grandparent_text'] = grandparent.select('text()').extract()[0]
            item['grandparent_url'] = grandparent.select('@href').extract()[0]

            # this will be considered lower than the main level, because these categories are very detailed
            item['level'] = -1

            items.append(item)

        for link in parent_links:

            # extract immediate parent of this link (first preceding sibling (of the parent node) with class='bullet2')
            parent = link.select("parent::node()/preceding-sibling::*[@class='bullet1'][1]/a")

            item = CategoryItem()
            item['text'] = link.select('text()').extract()[0]
            item['url'] = link.select('@href').extract()[0]

            item['parent_text'] = parent.select('text()').extract()[0]
            item['parent_url'] = parent.select('@href').extract()[0]

            # this will be considered the main level of the nested list (it's comparable with the main level of the other sitemaps)
            item['level'] = 0

            items.append(item)

        for link in grandparent_links:

            item = CategoryItem()
            item['text'] = link.select('text()').extract()[0]
            item['url'] = link.select('@href').extract()[0]

            item['level'] = 1

            items.append(item)

        return items

        

################################
# Run with 
#
# scrapy crawl bestseller
#
################################

# scrape bestsellers list and extract products
class BestsellerSpider(BaseSpider):
    name = "overstock_bestseller"
    allowed_domains = ["overstock.com"]
    start_urls = [
        'http://www.overstock.com/intlcountryselect?proceedasus=true&referer=http://www.overstock.com/top-sellers',
    ]

    def parse(self, response):
        hxs = HtmlXPathSelector(response)

        #TODO: !! select currency
        
        # extract tabs and their corresponding departments
        tabs = hxs.select("//ul[@id='tab-set']/li/a")

        departments = {}
        for tab in tabs:
            department_name = tab.select("text()").extract()[0]
            tab_id = tab.select("@href").extract()[0].replace("#","")
            departments[tab_id] = department_name

        # for each deparment extract products from corresponding tab
        for tab in departments:
            
            department = departments[tab]
            
            # in compound output the Jewelry department is missing because it is a duplicate of Watches

            products = hxs.select("//div[@id='%s']/div[@class='OProduct']" % tab)

            # counter to keep track of products rank
            rank = 0
            for product in products:

                item = ProductItem()
                item['department'] = department

                rank += 1
                item['rank'] = str(rank)

                product_link = product.select(".//div[@class='Oname']/a")

                product_name = product_link.select("text()").extract()
                product_url = product_link.select("@href").extract()

                if product_name:
                    item['list_name'] = product_name[0].strip()

                if product_url:
                    item['url'] = product_url[0]

                    # if there's no url move on to next product
                else:
                    continue

                #TODO: change price to USD
                price = product.select(".//div[@class='Oprice']/span[@class='Ovalue']/span[@class='Ovalue']/text()").extract()
                if price:
                    item['price'] = price[0]

                # pass the item to the parseProduct method
                request = Request(item['url'], callback = self.parseProduct)
                request.meta['item'] = item
                yield request

    def parseProduct(self, response):
        hxs = HtmlXPathSelector(response)

        item = response.meta['item']

        product_name = hxs.select("//h1/text()").extract()[0]
        page_title = hxs.select("//title/text()").extract()[0]

        # remove site name "Overstock.com" prom page title suffix
        m = re.match("(.*) \| Overstock\.com", page_title, re.UNICODE)
        if m:
            page_title = m.group(1).strip()

        item['product_name'] = product_name
        item['page_title'] = page_title

        # add date
        item['date'] = datetime.date.today().isoformat()

        yield item           
