from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from Categories.items import CategoryItem
import sys
import string

################################
# Run with 
#
# scrapy crawl sears
#
################################


class SearsSpider(BaseSpider):
    name = "sears"
    allowed_domains = ["coradrive.fr"]

    start_urls = ['http://www.coradrive.fr/']

    def __init__(self, outfile=None):
        self.outfile=outfile

        # level that is considered to contain departments
        self.DEPARTMENT_LEVEL = 1

    
    def parse(self, response):

        hxs = HtmlXPathSelector(response)
        #TODO: add departments with no subcategories!!

        # get urls of pages for each category
        urls = hxs.select("//div[@class='siteMapSubCell']//ul/li/a/@href").extract()

        # add departments to items
        departments = hxs.select("//div[@class='siteMapSubCell']//h4/a")
        items = []
        for department in departments:
            item = CategoryItem()
            item['text'] = department.select('text()').extract()[0]
            item['url'] = department.select('@href').extract()[0]
            item['level'] = 1
            items.append(item)

        # parse each page in urls list with parsePage
        # build urls by adding the prefix of the main page url
        first = True
        root_url = "http://www.sears.com/shc/s"
        for url in urls:
            request = Request(root_url + "/" + url, callback = self.parsePage)
            # send these only once (the first time)
            if first:
                request.meta['items'] = items
                first = False
            else:
                request.meta['items'] = []
            yield request

    # parse one page - extract items (categories)
    def parsePage(self, response):
        # currently selects only lowest level links, and their parents inside their fields
        hxs = HtmlXPathSelector(response)

        #TODO: add special categories if any

        # select lowest level categories
        links = hxs.select("//div[@class='siteMapSubCat']/ul/li/a")
        # select parent categories
        parent_links = hxs.select("//div[@class='siteMapSubCat']/h4/a")

        # extract page name by getting text in url after "=" symbol
        # example url: smv_10153_12605?vName=Appliances
        
        page_name = response.url.split("=")[1]

        # get partial list from previous function (containing departments)
        items = response.meta['items']
        root_url = "http://www.coradrive.fr/"

        for link in links:
            item = CategoryItem()
            item['page_text'] = page_name
            item['page_url'] = response.url
            # add the page as the grandparent category
            item['grandparent_text'] = page_name
            item['grandparent_url'] = response.url

            # extract parent category element
            parent = link.select("./parent::node()/parent::node()/preceding-sibling::node()[2]/a")
            parent_text = parent.select('text()').extract()
            parent_url = parent.select('@href').extract()
            if parent_text and parent_url:
                item['parent_text'] = parent_text[0]
                item['parent_url'] = root_url + parent_url[0]
            # if you can't find a parent here go to first of the previous columns that has a parent
            else:
                parent = link.select("./parent::node()/parent::node()/parent::node()/preceding-sibling::node()[2]/h4[last()]")
                parent_text = parent.select("a/text()").extract()
                parent_url = parent.select("a/@href").extract()
                index = 3
                while not parent_text:
                    parent = link.select("./parent::node()/parent::node()/parent::node()/preceding-sibling::node()[%d]/h4[last()]" % index)
                    index += 1
                    parent_text = parent.select("a/text()").extract()
                    parent_url = parent.select("a/@href").extract()
                item['parent_text'] = parent_text[0]
                item['parent_url'] = root_url + parent_url[0]

            item['text'] = link.select('text()').extract()[0]
            item['url'] = root_url + link.select('@href').extract()[0]

            # these are subcategories
            item['level'] = -1
            items.append(item)

        for link in parent_links:
            item = CategoryItem()
            item['text'] = link.select('text()').extract()[0]
            item['url'] = root_url + link.select('@href').extract()[0]

            item['page_text'] = page_name
            item['page_url'] = response.url
            # add the page as the parent category
            item['parent_text'] = page_name
            item['parent_url'] = response.url
            # this is considered to be the main category level
            item['level'] = 0

            items.append(item)

        # # add the page name as a department
        # item = CategoryItem()
        # item['text'] = page_name
        # item['url'] = response.url
        # item['page_text'] = page_name
        # item['page_url'] = response.url
        # item['level'] = 1

        # items.append(item)

        return items
