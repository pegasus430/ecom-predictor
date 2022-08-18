from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from Categories.items import CategoryItem
from scrapy.http import Request
from scrapy.http import TextResponse
import re
import sys

from spiders_utils import Utils

################################
# Run with 
#
# scrapy crawl macys
#
################################

# scrape sitemap list and retrieve categories
class MacysSpider(BaseSpider):
    name = "macys"
    allowed_domains = ["macys.com"]
    start_urls = [
        "http://www1.macys.com/cms/slp/2/Site-Index",
    ]

    def __init__(self, outfile=None):
        self.outfile = outfile

        # level that is considered to contain departments
        self.DEPARTMENT_LEVEL = 1


    def parse(self, response):
        hxs = HtmlXPathSelector(response)
        links = hxs.select("//div[@id='sitemap_header']/a")
        root_url = "http://www1.macys.com"

        department_id = 0

        for link in links:
            item = CategoryItem()

            text = link.select('text()').extract()[0]
            item['text'] = text
            # remove unnecessary suffix from URL
            url = link.select('@href').extract()[0]
            m = re.match("(.*\?id=[0-9]+)&?.*",url)
            if m:
                item['url'] = m.group(1)
            else:
                item['url'] = url
            item['level'] = 1

            # only yield this item after parsing its page and extracting additional info
            #yield item

            department_id += 1

            # create request to extract subcategories for this category
            yield Request(item['url'], callback = self.parseCategory, meta = {'parent' : item, 'level' : 1, \
                'department_text' : item['text'], 'department_url' : item['url'], 'department_id' : department_id})

    # extract subcategories from each category
    def parseCategory(self, response):
        hxs = HtmlXPathSelector(response)

        # output received parent element after extracting additional info
        item = response.meta['parent']

        # add department name, url and id to item
        item['department_text'] = response.meta['department_text']
        item['department_url'] = response.meta['department_url']
        item['department_id'] = response.meta['department_id']

        # extract number of items if available
        prod_count_holder = hxs.select("//span[@id='productCount']/text()").extract()
        if prod_count_holder:
            item['nr_products'] = int(prod_count_holder[0].strip())
        # exract description if available
        desc_holder = hxs.select("//div[@id='catalogCopyBlock']")
        if desc_holder:
            item['description_title'] = desc_holder.select("h2/text()").extract()[0]
            description_texts = desc_holder.select("p/text()").extract()

            # if the list is not empty and contains at least one non-whitespace item
            if description_texts and reduce(lambda x,y: x or y, [line.strip() for line in description_texts]):
                # replace all whitespace with one space, strip, and remove empty texts; then join them
                item['description_text'] = " ".join([re.sub("\s+"," ", description_text.strip()) for description_text in description_texts if description_text.strip()])

                tokenized = Utils.normalize_text(item['description_text'])
                item['description_wc'] = len(tokenized)

                (item['keyword_count'], item['keyword_density']) = Utils.phrases_freq(item['description_title'], item['description_text'])
            else:
                item['description_wc'] = 0

        else:
            item['description_wc'] = 0
        
        yield item

        chapters = hxs.select("//li[@class='nav_cat_item_bold']")
        
        for chapter in chapters:

            #TODO: still includes some special categories (like "Coming Soon" in men)
            # exclude "Brands" chapter
            chapter_name = chapter.select("span/text()").extract()
            if not chapter_name or "brands" in chapter_name[0]:
                continue

            subcats = chapter.select("ul/li/a")
            for subcat in subcats:
                item = CategoryItem()
                text = subcat.select('text()').extract()[0]
                # if it starts with "Shop all", ignore it
                if re.match("Shop [aA]ll.*", text):
                    continue
                else:
                    item['text'] = text
                # remove unnecessary suffix from URL
                url = subcat.select('@href').extract()[0]
                m = re.match("(.*\?id=[0-9]+)&?.*",url)
                if m:
                    item['url'] = m.group(1)
                else:
                    item['url'] = url
                item['level'] = int(response.meta['level']) - 1
                item['parent_text'] = response.meta['parent']['text']
                item['parent_url'] = response.url

                #yield item

                yield Request(item['url'], callback = self.parseCategory, meta = {'parent' : item, 'level' : item['level'], \
                    'department_text' : response.meta['department_text'], 'department_url' : response.meta['department_url'], 'department_id' : response.meta['department_id']})
