from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from Categories.items import CategoryItem
from Categories.items import ProductItem
from scrapy.http import Request
from scrapy.http import Response
import re
import sys
import datetime

from spiders_utils import Utils


################################
# Run with 
#
# scrapy crawl amazon_bestseller
#
################################

# crawl bestsellers lists and extract product name, price, department etc
class BestsellerSpider(BaseSpider):
    name = "amazon_bestseller"
    allowed_domains = ["amazon.com"]
    start_urls = [
        "http://www.amazon.com/Best-Sellers/zgbs/ref=zg_bs_unv_mas_0_mas_1",
    ]

    # get main pages for department bestseller pages and pass them to the parsePage function
    def parse(self, response):
        # currently extracting all from bestsellers menu (only departments level)
        # and from manually building URLs from each sitemap department (doesn't work for all)
        #TODO: extract lower levels from bestsellers menu
        #TODO: some more matching between sitemap departments names and bestsellers menu names

        hxs = HtmlXPathSelector(response)
        department_links = hxs.select("//ul[@id='zg_browseRoot']/ul/li/a")

        departments = []

        # extract department name and url for each department in menu
        #TODO: add info about availability?
        
        for department_link in department_links:
            department = {"url" : department_link.select("@href").extract()[0], "text" : department_link.select("text()").extract()[0]}
            departments.append(department)
        
        # pass department urls to parsePage (35 departments)
        for department in departments:
            request = Request(department['url'], callback = self.parsePage)
            request.meta['dept_name'] = department['text']
            yield request

        # get departments from sitemap and search for bestsellers for each
        sitemap_url = "http://www.amazon.com/gp/site-directory/ref=sa_menu_top_fullstore"
        yield Request(sitemap_url, callback = self.getDepartmentsBs)


    # get bestsellers pages for sitemap departments, if found
    # (by passing department pages to getDepartmentBs to get bestsellers list for each)
    def getDepartmentsBs(self, response):
        hxs = HtmlXPathSelector(response)
        department_links = hxs.select("//div[@id='siteDirectory']//table//a")

        departments = []
        root_url = "http://www.amazon.com"

        for department_link in department_links:
            department = {"url" : root_url + department_link.select("@href").extract()[0], "text" : department_link.select("text()").extract()[0]}
            departments.append(department)

        # pass department urls to getDepartmentBs to get bestsellers for a particular department
        for department in departments:
            request = Request(department['url'], callback = self.getDepartmentBs)
            request.meta['dept_name'] = department['text']
            yield request

    # get bestsellers page for one department
    # receive a request to its page, and get bestsellers list if found, pass it to parsePage
    def getDepartmentBs(self, response):
        hxs = HtmlXPathSelector(response)

        dept_name = response.meta['dept_name']
        root_url = "http://www.amazon.com"

        # # searching for bestsellers tab in the menu doesn't really work (it leads to the parent's bestsellers)
        # menuitems = hxs.select("//div[@id='nav-bar-inner']//li[@class='nav-subnav-item']/a")
        # for menuitem in menuitems:

        #     # if we find a menu item with the text "Best Sellers", pass that link to be parsed
        #     name = menuitem.select("text()").extract()[0].strip()
        #     if name == 'Best Sellers':
        #         url = root_url + menuitem.select("@href").extract()[0]
        #         department = {"text" : dept_name, "url" : url}

        #         request = Request(department['url'], callback = self.parsePage)
        #         request.meta['dept_name'] = department['text']
        #         yield request

        #         break

        # try to build URLs similar to this "http://www.amazon.com/Best-Sellers-Books-Audiobooks/zgbs/books/368395011"
        # by replacing the number with each category's number

        # extract category number
        template_url = "http://www.amazon.com/Best-Sellers-Books-Audiobooks/zgbs/books/368395011"
        m_source = re.match("(.*)\&node=([0-9]+)", response.url)
        if m_source:
            m_dest = re.match("(.*)/([0-9]+)", template_url)
            if m_dest:
                str_source = m_source.group(2)
                str_dest = m_dest.group(2)
                page_url = template_url.replace(str_dest, str_source)

                request = Request(page_url, callback = self.parsePage)
                request.meta['dept_name'] = dept_name
                yield request

            else:
                print "NOT MATCHED", template_url
        else:
            print "NOT MATCHED", response.url


    # extract each page url for a department's bestseller list and pass it to parseDepartment
    def parsePage(self, response):
        hxs = HtmlXPathSelector(response)
        
        # for MP3 Downloads, rerun this method with its subcategories (MP3 Songs and MP3 Albums). also split it into paid and free?
        if response.meta['dept_name'] == "MP3 Downloads":
            subcategories = hxs.select("//ul[@id='zg_browseRoot']/ul/ul/li/a")
            # only select first subcategory (paid albums)
            for subcategory in [subcategories[0]]:
                request = Request(subcategory.select("@href").extract()[0], callback = self.parsePage)

                # match between bestsellers menu name and sitemap name
                dept_name = "MP3 Music Store"
                request.meta['dept_name'] = dept_name#subcategory.select("text()").extract()[0]
                yield request

        else:
            page_urls = hxs.select("//div[@id='zg_paginationWrapper']//a/@href").extract()

            for page_url in page_urls:
                request = Request(page_url, callback = self.parseDepartment)
                request.meta['dept_name'] = response.meta['dept_name']
                yield request

    # take a page of a department's bestsellers list and extract products
    def parseDepartment(self, response):
        hxs = HtmlXPathSelector(response)
        products = hxs.select("//div[@class='zg_itemImmersion']")

        items = []

        for product in products:
            item = ProductItem()

            #TODO: the index for the title is sometimes out of range - sometimes it can't find that tag (remove the [0] to debug)
            list_name = product.select("div[@class='zg_itemWrapper']//div[@class='zg_title']/a/text()").extract()
            if list_name:
                item['list_name'] = list_name[0]
            else:
                # if there's no product name don't include this product in the list, move on to the next
                continue

            url = product.select("div[@class='zg_itemWrapper']//div[@class='zg_title']/a/@href").extract()
            if url:
                item['url'] = url[0].strip()
            else:
                # if there's no product url don't include this product in the list, move on to the next
                # one of the products in Lawn & Garden is missing a name and url, also in Sports & Outdoors
                continue
            
            #TODO: this needs to be refined, many prices etc. extract all prices? new, used etc
            prices = product.select("div[@class='zg_itemWrapper']//div[@class='zg_price']")

            price = prices.select("strong[@class='price']/text()").extract()
            listprice = prices.select("span[@class='listprice']/text()").extract()

            # some of the items don't have a price
            if price:
                item['price'] = price[0]

            # some items don't have a "list price"
            if listprice:
                item['listprice'] = listprice[0]

            # extract rank and ignore last character of the string (it's .)
            item['rank'] = product.select(".//span[@class='zg_rankNumber']/text()").extract()[0][:-1]

            #dept_name = hxs.select("//ul[@id='zg_browseRoot']//span[@class='zg_selected']/text()").extract()[0].strip()
            item['department'] = response.meta['dept_name']#dept_name

            # add url of bestsellers page this was found on
            item['bspage_url'] = response.url

            # pass the item to the parseProduct function to extract info from product page
            request = Request(item['url'], callback = self.parseProduct)
            request.meta['item'] = item

            yield request


    # extract info from product page
    def parseProduct(self, response):
        hxs = HtmlXPathSelector(response)

        item = response.meta['item']

        # find title of product page
        page_title = hxs.select("//title/text()").extract()[0]

        # Remove "Amazon.com" from title, to leave only the prouct's name

        # handle all cases (titles come in different formats)
        
        # format 1
        m1 = re.match("(.*)[-:] Amazon\.com(.*)", page_title, re.UNICODE)
        if m1:
            page_title = m1.group(1).strip() + m1.group(2)

        # format 2
        m2 = re.match("Amazon\.com ?: (.*)", page_title, re.UNICODE)
        if m2:
            page_title = m2.group(1)

        # Remove department name from page title if found

        # there are some other suffixes after : , that are not always the same department's name (like ": Kitchen & Dining" in an Appliances product)
        
        # m = re.match("(.*): " + item['department'], page_title, re.UNICODE)
        # if m:
        #     page_title = m.group(1)

        #TODO: handle special characters, like trademark symbol; also output them as unicode strings in the output file
        
        item['page_title'] = page_title


        # find product name on product page (5 possible formats)
        product_name = hxs.select("//span[@id='btAsinTitle']/text()").extract()
        if not product_name:
            product_name = hxs.select("//h1[@id='title']/text()").extract()
        if not product_name:
            product_name = hxs.select("//h1[@class='parseasinTitle']/text()").extract()
        if not product_name:
            product_name = hxs.select("//h1[@class='parseasintitle']/text()").extract()

        # for the movies department it's only a h1
        if not product_name:
            product_name = hxs.select("//h1/text()").extract()
        # if not product_name:
        #     product_name = "nume"
        # else:
        item['product_name'] = product_name[0].strip()

        # add date
        item['date'] = datetime.date.today().isoformat()

        return item
