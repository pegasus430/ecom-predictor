from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from Categories.items import CategoryItem
import sys

################################
# Run with 
#
# scrapy crawl bjs
#
################################


class BJsSpider(BaseSpider):
    name = "bjs"
    allowed_domains = ["bjs.com"]
    start_urls = [
        "http://www.bjs.com/webapp/wcs/stores/servlet/SiteMapView?langId=-1&storeId=10201&catalogId=10001",
        #"file:///home/ana/code/nlp_reviews/misc/the_pages/BJ's%20Wholesale%20Club.html"
    ]

    def __init__(self, outfile=None):
        self.outfile = outfile

        # level that is considered to contain departments
        self.DEPARTMENT_LEVEL = 1


    def parse(self, response):
        hxs = HtmlXPathSelector(response)
        # extract all bottom level categories
        links = hxs.select("//div[@class='links']//a")
        # extract parent categories
        parent_links = hxs.select("//div[@class='header_no_icon']")
        items = []

        for link in links:

            # extract parent category
            parent = link.select("parent::node()/parent::node()/parent::node()/div/div[position()=1]/a")

            item = CategoryItem()
            item['text'] = link.select('text()').extract()[0]
            item['url'] = link.select('@href').extract()[0]

            parent_text = parent.select('h2/text()').extract()
            parent_url = parent.select('@href').extract()
            if parent_text:
                item['parent_text'] = parent_text[0]
            if parent_url:
                item['parent_url'] = parent_url[0]

            item['level'] = 0

            items.append(item)

        for parent in parent_links:
            item = CategoryItem()
            item['text'] = parent.select('a/h2/text()').extract()[0]
            item['url'] = parent.select('a/@href').extract()[0]
            item['level'] = 1

            items.append(item)

        return items
