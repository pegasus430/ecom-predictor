from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from Categories.items import CategoryItem
from Categories.items import ProductItem
from scrapy.http import Request
from scrapy.http import Response
import re
import sys

from spiders_utils import Utils

################################
# Run with 
#
# scrapy crawl sherwin
#
################################

# crawls sitemap and extracts department and categories names and urls (as well as other info)
class SherwinSpider(BaseSpider):
    name = "sherwin"
    allowed_domains = ["sherwin-williams.com"]
    start_urls = [
        "https://www.sherwin-williams.com/sitemap/",
    ]

    def __init__(self, outfile=None):

        self.outfile = outfile

        self.base_url = "http://www.sherwin-williams.com"
        
        # level that is considered to contain departments
        self.DEPARTMENT_LEVEL = 1


    def parse(self, response):
        hxs = HtmlXPathSelector(response)

        # extract departments
        departments = hxs.select("//h2")
        department_id = 0
        for department in departments:
            department_item = CategoryItem()
            department_text = department.select("text()").extract()[0]

            department_item['department_text'] = department_text

            # #TODO: add department_url, from sherwin-williams.com ...? get department list from there and match with departments from here by seeing if names match

            department_item['department_id'] = department_id

            department_item['text'] = department_text

            department_item['level'] = 1


            # get categories in department
            categories = department.select("following-sibling::ul[1]/li")

            # extract department url from one of its categories urls (it's not available directly)
            category_ex = categories[0]
            category_ex_url = Utils.add_domain(category_ex.select("a/@href").extract()[0], self.base_url)
            # extract first part of url
            m = re.match("(http://www.sherwin\-williams\.com/[^/]+)/.*", category_ex_url)
            department_url = m.group(1)
            department_item['department_url'] = department_url
            department_item['url'] = department_url

            for category in categories:
                item = CategoryItem()
                #TODO: special if 'Services'? or Specifications, or Ads...
                category_text = category.select("a/text()").extract()[0]
                category_url =  Utils.add_domain(category.select("a/@href").extract()[0], self.base_url)
                item['text'] = category_text
                item['url'] = category_url

                # if it's not a 'products' category, mark it and all its subcategories as special

                if category_text != 'Products':
                    item['special'] = 1
                    special = True
                else:
                    special = False

                item['department_id'] = department_id
                item['department_text'] = department_text
                item['department_url'] = department_url

                item['parent_text'] = department_text
                item['parent_url'] = department_url

                item['level'] = 0

                #TODO: do we need description_wc here as well?

                yield Request(item['url'], callback = self.parseCategory, meta = {'item' : item})

                # get subcategories in category
                subcategories = category.select("ul/li")
                for subcategory in subcategories:
                    item = CategoryItem()

                    item['text'] = subcategory.select("a/text()").extract()[0]
                    item['url'] = Utils.add_domain(subcategory.select("a/@href").extract()[0], self.base_url)

                    item['department_id'] = department_id
                    item['department_text'] = department_text
                    item['department_url'] = department_url

                    item['parent_text'] = category_text
                    item['parent_url'] = category_url

                    item['level'] = -1

                    # if parent is special, category is special
                    if special:
                        item['special'] = 1

                    yield Request(item['url'], callback = self.parseSubcategory, meta = {'item' : item})

            department_id += 1

            # return department
            yield department_item

    def parseCategory(self, response):
        hxs = HtmlXPathSelector(response)

        item = response.meta['item']

        #TODO: test if this xpath should include other types of pages
        description_text_holder = hxs.select("//p[@class='subtitle grey']/text()").extract()
        description_title_holder = hxs.select("//h1/text()[normalize-space()!='']").extract()

        if description_text_holder:
            item['description_text'] = description_text_holder[0]
            item['description_title'] = description_title_holder[0]

            description_tokenized = Utils.normalize_text(item['description_text'])
            item['description_wc'] = len(description_tokenized)

            (item['keyword_count'], item['keyword_density']) = Utils.phrases_freq(item['description_title'], item['description_text'])
        else:
            item['description_wc'] = 0

        yield item


    def parseSubcategory(self, response):
        hxs = HtmlXPathSelector(response)

        subcategory = response.meta['item']

        # yield this subcategory
        yield subcategory

        # if subcategory was special, we'll mark all subsubcategories as special
        if 'special' in subcategory:
            special = True
        else:
            special = False

        # get its subcategories
        subsubcategories = hxs.select("//div[@class='product-category-expanded']//h3[@class='title']")

        for subsubcategory in subsubcategories:
            item = CategoryItem()
            item['text'] = subsubcategory.select("a/text()").extract()[0]
            item['url'] = Utils.add_domain(subsubcategory.select("a/@href").extract()[0], self.base_url)

            if special:
                item['special'] = 1

            item['parent_text'] = subcategory['text']
            item['parent_url'] = subcategory['url']
            item['department_text'] = subcategory['department_text']
            item['department_url'] = subcategory['department_url']
            item['department_id'] = subcategory['department_id']

            item['level'] = subcategory['level'] - 1

            description_text_holder = subsubcategory.select("following-sibling::p[@class='description'][1]/text()").extract()
            if description_text_holder:
                item['description_text'] = description_text_holder[0]
                item['description_title'] = item['text']
                description_tokenized = Utils.normalize_text(item['description_text'])
                item['description_wc'] = len(description_tokenized)

                (item['keyword_count'], item['keyword_density']) = Utils.phrases_freq(item['description_title'], item['description_text'])

            else:
                item['description_wc'] = 0

            # parse subcategory page to get product count, or further subsubcategory
            yield Request(item['url'], callback = self.parseSubcategoryPage, meta = {'item' : item})

    def parseSubcategoryPage(self, response):
        hxs = HtmlXPathSelector(response)
        item = response.meta['item']

        # if there is a product count, we reached the final page and can stop (after returning the subcategory)
        product_count_holder = hxs.select("//li[@class='count']//text()[normalize-space()!='']").re("(?<=of )[0-9]+")

        if product_count_holder:
            item['nr_products'] = int(product_count_holder[0])

            # return item (we reached the end)
            yield item

        # if there is no product category, assume there is a further subcategory; so send it back to parseCategory as well as returning it as a subcategory (below)
        else:
            # return this subcategory anyway
            yield item

            # then pass it to parseSubcategory to pe parsed for subsubcategories
            yield Request(response.url, callback = self.parseSubcategory, meta = response.meta)
