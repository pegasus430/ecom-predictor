from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from Categories.items import CategoryItem
from Categories.items import ProductItem
from scrapy.http import Request
import re
import sys
import datetime

from spiders_utils import Utils

################################
# Run with 
#
# scrapy crawl newegg
#
################################

# crawl sitemap and extract products and categories
class NeweggSpider(BaseSpider):
    name = "newegg"
    allowed_domains = ["newegg.com"]
    start_urls = ["http://www.newegg.com"]

    def __init__(self, outfile=None):
        self.outfile = outfile

        # level that is considered to contain departments
        self.DEPARTMENT_LEVEL = 1

    # remove suffix (referrer?) from URL
    def clean_url(self, url):
        m = re.match("(.*)\?Tid=[0-9]+", url)
        if m:
            return m.group(1)
        else:
            return url

    def parse(self, response):
        hxs = HtmlXPathSelector(response)

        category_links = hxs.select("//div[@class='itmNav']//a")

        # unique ids for departments
        department_id = 0

        for category_link in category_links:

            item = CategoryItem()
            category_name = category_link.select("text()").extract()
            if category_name:
                item['text'] = category_name[0]
            else:
                sys.stderr.write("Error: no name for category in element " + category_link.extract())
                continue
            item['url'] = self.clean_url(category_link.select("@href").extract()[0])
            # mark as department
            item['level'] = 1

            department_id += 1

            # mark it as its own department, will be passed on to its subcategories
            item['department_text'] = item['text']
            item['department_url'] = item['url']
            item['department_id'] = department_id

            #items.append(item)
            yield Request(url = item['url'], callback = self.parseCategory, meta = {"item" : item, \
                'department_text' : item['department_text'], 'department_url' : item['department_url'], 'department_id' : item['department_id']})

        #return items

    def parseCategory(self, response):
        hxs = HtmlXPathSelector(response)

        item = response.meta['item']

        # extract number of products if available
        #TODO check
        count_holder = hxs.select("//div[@class='recordCount']/span[@id='RecordCount_1']/text()")
        if count_holder:
            item['nr_products'] = int(count_holder.extract()[0])

        #TODO
        # try to change URL "Category" to "SubCategory", see if you find the product count there

        # extract description if available
        description_holders = hxs.select("//div[@id='bcaShopWindowSEO']")
        # if the list is not empty and contains at least one non-whitespace item
        if description_holders:
            description_texts = description_holders.select(".//text()[not(ancestor::h2)]").extract()

            # replace all whitespace with one space, strip, and remove empty texts; then join them
            item['description_text'] = " ".join([re.sub("\s+"," ", description_text.strip()) for description_text in description_texts if description_text.strip()])

            tokenized = Utils.normalize_text(item['description_text'])
            item['description_wc'] = len(tokenized)

            description_title = description_holders.select(".//h2/text()").extract()
            if description_title:
                item['description_title'] = description_title[0].strip()

                (item['keyword_count'], item['keyword_density']) = Utils.phrases_freq(item['description_title'], item['description_text'])
        else:
            item['description_wc'] = 0

        yield item

        parent = item

        #TODO
        # extract and parse subcategories
        subcats = hxs.select("//dl[@class='categoryList primaryNav']/dd/a")
        for subcat in subcats:
            item = CategoryItem()
            
            item['text'] = subcat.select("text()").extract()[0].strip()

            #TODO: check out some huge URLs
            item['url'] = self.clean_url(subcat.select("@href").extract()[0])

            item['parent_text'] = parent['text']
            item['parent_url'] = parent['url']
            item['level'] = parent['level'] - 1
            item['department_text'] = response.meta['department_text']
            item['department_url'] = response.meta['department_url']
            item['department_id'] = response.meta['department_id']

            yield Request(url = item['url'], callback = self.parseCategory, meta = {"item" : item, \
                "department_text" : response.meta['department_text'], "department_url" : response.meta['department_url'], "department_id" : response.meta['department_id']})
