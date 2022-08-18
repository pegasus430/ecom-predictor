from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from Categories.items import CategoryItem
from scrapy.http import Request
import sys
import re
from spiders_utils import Utils

################################
# Run with 
#
# scrapy crawl tigerdirect
#
################################


class TigerdirectSpider(BaseSpider):
    name = "tigerdirect"
    allowed_domains = ["tigerdirect.com"]
    start_urls = [
        "http://www.tigerdirect.com/computerproducts.asp",
    ]

    def __init__(self, outfile=None):

        self.outfile = outfile

        self.parsed_urls = []
        
        # level that is considered to contain departments
        self.DEPARTMENT_LEVEL = 1


    def parse(self, response):
        hxs = HtmlXPathSelector(response)
        links = hxs.select("//table//tr[1]/td//a[ancestor::h4]")

        department_id = 0

        for link in links:
            item = CategoryItem()
            item['text'] = link.select('text()').extract()[0]
            item['url'] = link.select('@href').extract()[0]
            item['level'] = 1

            department_id += 1
            item['department_text'] = item['text']
            item['department_url'] = item['url']
            item['department_id'] = department_id

            yield Request(url = item['url'], callback = self.parseCategory, meta = {'item' : item,\
             'department_url' : item['department_url'], 'department_text' : item['department_text'], 'department_id' : department_id})

    # receive one category url, add aditional info and return it; then extract its subcategories and parse them as well
    def parseCategory(self, response):
        hxs = HtmlXPathSelector(response)

        item = response.meta['item']

        # extract number of products if available
        nrproducts_holder = hxs.select("//div[@class='resultsfilterBottom']/div[@class='itemsShowresult']/strong[2]/text()").extract()
        if nrproducts_holder:
            item['nr_products'] = int(nrproducts_holder[0])

        # extract description if available
        description_holders = hxs.select("//div[@class='textBlock']")
        # if the list is not empty and contains at least one non-whitespace item
        if description_holders:
            description_texts = description_holders.select(".//text()[not(ancestor::h2)]").extract()

            # replace all whitespace with one space, strip, and remove empty texts; then join them
            desc_text = " ".join([re.sub("\s+"," ", description_text.strip()) for description_text in description_texts if description_text.strip()])
            if desc_text:
                item['description_text'] = desc_text

                tokenized = Utils.normalize_text(item['description_text'])
                item['description_wc'] = len(tokenized)
            else:
                item['description_wc'] = 0

            description_title = description_holders.select(".//h2/text()").extract()
            if description_title:
                item['description_title'] = description_title[0].strip()

                if desc_text:

                    (item['keyword_count'], item['keyword_density']) = Utils.phrases_freq(item['description_title'], item['description_text'])
        else:
            item['description_wc'] = 0

        self.parsed_urls.append(item['url'])

        yield item

        # extract subcategories
        product_links = hxs.select("//div[@class='resultsWrap listView']//h3[@class='itemName']/a/@href").extract()
        # only extract subcategories if product links not found on page
        if not product_links:

            parent = item

            # search for a link to "See All Products"
            seeall = hxs.select("//span[text()='See All Products']/parent::node()/@href").extract()
            if seeall:
                # pass the page with subcategories menu to a method to parse it
                #print 'parsing seeall: from ', response.url, ' to ', Utils.add_domain(seeall[0], "http://www.tigerdirect.com")
                yield Request(url = Utils.add_domain(seeall[0], "http://www.tigerdirect.com"), callback = self.parseSubcats, \
                    meta = {'parent' : parent,\
                     'department_text' : response.meta['department_text'], 'department_url' : response.meta['department_url'],\
                     'department_id' : response.meta['department_id']})
            else:
                # pass the current page (with subcategories menu on it) to a method to parse it
                #print 'parsing for subcategories ', response.url
                yield Request(url = response.url, callback = self.parseSubcats, meta = {'parent' : parent,\
                    'department_text' : response.meta['department_text'], 'department_url' : response.meta['department_url'],\
                    'department_id' : response.meta['department_id']})

    
    def parseSubcats(self, response):
        hxs = HtmlXPathSelector(response)

        parent = response.meta['parent']

        # extract subcategories
        subcats_links = hxs.select("//div[@class='sideNav']/div[@class='innerWrap'][1]//ul/li/a")
        for subcat_link in subcats_links:
            item = CategoryItem()

            item['url'] = Utils.add_domain(subcat_link.select("@href").extract()[0], "http://www.tigerdirect.com")
            item['text'] = subcat_link.select("text()").extract()[0]

            item['parent_text'] = parent['text']
            item['parent_url'] = parent['url']
            item['level'] = parent['level'] - 1

            item['department_text'] = response.meta['department_text']
            item['department_id'] = response.meta['department_id']
            item['department_text'] = response.meta['department_text']

            #print 'passing to parse category ', item

            # there are some loops in their categories tree, so we need to check this to avoid infinite loops in crawling
            if item['url'] not in self.parsed_urls:
                yield Request(url = item['url'], callback = self.parseCategory,\
                 meta = {'item' : item,\
                 'department_text' : response.meta['department_text'], 'department_url' : response.meta['department_url'],\
                  'department_id' : response.meta['department_id']})