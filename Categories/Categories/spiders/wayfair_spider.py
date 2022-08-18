from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from Categories.items import CategoryItem
from Categories.items import ProductItem
import datetime
import sys
import re

################################
# Run with 
#
# scrapy crawl wayfair
#
################################

# scrape sitemap and extract categories
class WayfairSpider(BaseSpider):
    name = "wayfair"
    allowed_domains = ["wayfair.com"]
    start_urls = [
        "http://www.wayfair.com/site_map.php",
    ]

    def __init__(self, outfile=None):
        self.DEPARTMENT_LEVEL = 1
        self.outfile = outfile

    def parse(self, response):
        hxs = HtmlXPathSelector(response)

        # select category links on all 3 levels
        links = hxs.select("//div[@class='categories']/ul/li/ul/li/ul/li/a")
        parent_links = hxs.select("//div[@class='categories']/ul/li/ul/li/a")
        grandparent_links = hxs.select("//div[@class='categories']/ul/li/a")

        # select special section "browse by brand"
        special_links = hxs.select("//div[@class='brands']/ul/li/ul/li/a")
        special_parent_links = hxs.select("//div[@class='brands']/ul/li/a")
        items = []

        for link in links:
            # extracting parents
            parent = link.select('parent::node()/parent::node()/parent::node()/a')
            # extracting grandparents
            grandparent = parent.select('parent::node()/parent::node()/parent::node()/a')
            
            item = CategoryItem()
            item['text'] = link.select('text()').extract()[0]
            item['url'] = link.select('@href').extract()[0]

            item['parent_text'] = parent.select('text()').extract()[0]
            item['parent_url'] = parent.select('@href').extract()[0]

            grandparent_text = grandparent.select('text()').extract()
            grandparent_url = grandparent.select('@href').extract()
            if grandparent_text:
                item['grandparent_text'] = grandparent_text[0]
            if grandparent_url:
                item['grandparent_url'] = grandparent_text[0]

            # this is considered more detailed than the main category level (compared to other sitemaps)
            item['level'] = -1

            items.append(item)

        for link in parent_links:
            # extracting parents
            parent = link.select('parent::node()/parent::node()/parent::node()/a')
            
            item = CategoryItem()
            item['text'] = link.select('text()').extract()[0]
            item['url'] = link.select('@href').extract()[0]

            parent_text = parent.select('text()').extract()
            parent_url = parent.select('@href').extract()
            if (parent_text):
                item['parent_text'] = parent_text[0]
            if (parent_url):
                item['parent_url'] = parent_url[0]

            # this is considered the main category level
            item['level'] = 0

            items.append(item)

        # last 2 categories need to be marked as special
        for link in grandparent_links[:-2]:
            item = CategoryItem()
            item['text'] = link.select('text()').extract()[0]
            item['url'] = link.select('@href').extract()[0]

            item['level'] = 1

            items.append(item)

        for link in grandparent_links[-2:]:
            item = CategoryItem()
            item['text'] = link.select('text()').extract()[0]
            item['url'] = link.select('@href').extract()[0]

            item['level'] = 1
            item['special'] = 1

            items.append(item)


        for link in special_links:
            # extracting parents
            parent = link.select('parent::node()/parent::node()/parent::node()/a')

            item = CategoryItem()
            item['text'] = link.select('text()').extract()[0]
            item['url'] = link.select('@href').extract()[0]

            parent_text = parent.select('text()').extract()
            parent_url = parent.select('@href').extract()
            if (parent_text):
                item['parent_text'] = parent_text[0]
            if (parent_url):
                item['parent_url'] = parent_url[0]

            # this is considered the main category level
            item['level'] = 0
            item['special'] = 1

            items.append(item)

        for link in special_parent_links:
            item = CategoryItem()
            item['text'] = link.select('text()').extract()[0]
            item['url'] = link.select('@href').extract()[0]

            item['level'] = 1
            item['special'] = 1

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
    name = "wayfair_bestseller"
    allowed_domains = ["wayfair.com"]
    start_urls = [
        "http://www.wayfair.com/Best-Sellers-l951.html?keyword=&dept=0&sortby=1&itemsperpage=40",
    ]

    def parse(self, response):
        hxs = HtmlXPathSelector(response)

        # extract page links and pass them to parsePage to parse each results page, also pass the current one
        request = Request(response.url, callback = self.parsePage)

        # send page number to parsePage
        request.meta['page'] = 1
        yield request

        pages = hxs.select("//span[@class='pagenumbers']/a")

        for page_i in range(len(pages)):
            url = pages[page_i].select("@href").extract()[0]
            request = Request(url, callback = self.parsePage)

            # send page number to parsePage (starts from page 2)
            request.meta['page'] = page_i + 2
            yield request

    def parsePage(self, response):
        #TODO: add department?

        hxs = HtmlXPathSelector(response)
        products = hxs.select("//li[@class='productbox']")

        products_per_page = 40
        page_nr = response.meta['page']

        # counter to keep track of product rank
        rank = 0

        for product in products:
            item = ProductItem()

            rank += 1

            product_link = product.select(".//a[@class='toplink']")
            url = product_link.select("@href").extract()
            if url:
                item['url'] = url[0]
            else:
                continue

            item['SKU'] = product.select("@data-sku").extract()[0]

            # compute global item rank using rank on current page and page number
            item['rank'] = str((page_nr - 1) * products_per_page + rank)

            product_name = product_link.select("div[@class='prodname']/text()").extract()
            brand_name = product_link.select("div[@class='prodname']/div[@class='prodbrandname emphasis']/text()").extract()

            if product_name:
                item['list_name'] = product_name[0].strip()
            if brand_name:
                item['brand'] = brand_name[0].strip()

            #TODO: also "Reg price", extract that as well?
            listprice = product.select(".//div[@class='wasprice']/span/text()").extract()
            if listprice:
                item['listprice'] = listprice[0]

            price = product.select(".//div[@class='price secondarytext midtitle']/text() | .//div[@class='price noticetext midtitle']/text()").extract()
            if price:
                item['price'] = price[0]

            # add date
            item['date'] = datetime.date.today().isoformat()

            # pass item to parseProduct method
            request = Request(item['url'], callback = self.parseProduct)
            request.meta['item'] = item
            yield request

    def parseProduct(self, response):
        hxs = HtmlXPathSelector(response)

        item = response.meta['item']

        # this is only the name, without the brand
        product_name = hxs.select("//h1/text()").extract()[0].strip()
        page_title = hxs.select("//title/text()").extract()[0]

        # remove "Wayfair.com" suffix from page name
        m = re.match("(.*) \| Wayfair", page_title, re.UNICODE)
        if m:
            page_title = m.group(1).strip()

        item['page_title'] = page_title
        item['product_name'] = product_name

        yield item
