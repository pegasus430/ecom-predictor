from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from scrapy.http import TextResponse
from Caturls.items import ProductItem
from Caturls.spiders.caturls_spider import CaturlsSpider
from pprint import pprint
from scrapy import log

from spiders_utils import Utils

import re
import sys

import urllib
import urlparse

################################
# Run with 
#
# scrapy crawl tesco -a cat_page="<url>" [-a outfile="<filename>" -a brands_file="<brands_filename>"]
# 
# (if specified, brands_filename contains list of brands that should be considered - one brand on each line. other brands will be ignored)
#
################################

#TODO: Notice! Some products are not part of any brand; the crawler extracts only using brand filters and if product is not under any brand then it will not be extracted


class TescoSpider(CaturlsSpider):

    name = "tesco"
    allowed_domains = ["tesco.com"]

    # tesco haircare
    #self.start_urls = ["http://www.tesco.com/direct/health-beauty/hair-care/cat3376671.cat?catId=4294961777"]

    # add brand option
    def __init__(self, cat_page, outfile = "product_urls.csv", use_proxy = False, brands_file=None):
        super(TescoSpider, self).__init__(cat_page=cat_page, outfile=outfile, use_proxy=use_proxy)

        self.base_url = "http://www.tesco.com"

        self.brands = []
        self.brands_normalized = []
        # if a file with a list of specific brands is specified, add them to a class field
        if brands_file:
            brands_file_h = open(brands_file, "r")
            for line in brands_file_h:
                self.brands.append(line.strip())
            brands_file_h.close()

            self.brands_normalized = reduce(lambda x, y: x+y, map(lambda x: self.brand_versions_fuzzy(x), self.brands))

        # this spider uses classification by product
        self.with_categories = True

    # parse category page - extract subcategories, send their url to be further parsed (to parseSubcategory)
    def parse(self, response):
        hxs = HtmlXPathSelector(response)

        subcats_links = hxs.select("//h2[contains(text(),'categories')]/following-sibling::ul[1]/li/a")
        for subcat_link in subcats_links:
            # extract name
            subcat_name = subcat_link.select("span/text()").extract()[0].strip()
            # extract url, add domain
            subcat_url = Utils.add_domain(subcat_link.select("@href").extract()[0], self.base_url)

            # send subcategories to be further parsed
            # if brand filter is set, senf to parseSubcategory for brands to be extracted etc
            if self.brands:
                yield Request(url = subcat_url, callback = self.parseSubcategory, meta = {'category' : subcat_name})
            # if brand filter is not set, send directly to extract products
            else:
                yield Request(url = subcat_url, callback = self.parseBrandPage, meta = {'category' : subcat_name})

    # parse subcategory page - extract urls to brands menu page; or directly to brands pages (if all available on the page)
    def parseSubcategory(self, response):
        hxs = HtmlXPathSelector(response)

        #print "SUBCATEGORY:", response.url

        # extract link to page containing brands (look for link to 'more')
        brands_menu_page = hxs.select("//h4[contains(text(),'Brand')]/following-sibling::ul[1]/li[@class='more']/a/@data-overlay-url").extract()

        if brands_menu_page:
            # send request for brands pages to be extracted
            yield Request(url = Utils.add_domain(brands_menu_page[0], self.base_url), callback = self.parseBrandsMenu, meta = {'category' : response.meta['category']})
        else:

            # if no 'more' link, extract brand pages directly from this page (it means they are all here)
            brands_pages = hxs.select("//h4[contains(text(),'Brand')]/following-sibling::ul[1]/li/a")

            for brand_page in brands_pages:
                brand_name = brand_page.select("span[@class='facet-str-name']/text()").extract()[0]
                brand_url = Utils.add_domain(brand_page.select("@href").extract()[0], self.base_url)

                # filter brands if it applies
                if self.brands and not self.name_matches_brands(brand_name):
                    self.log("Omitting brand " + brand_name, level=log.INFO)
                    continue

                # send request for brands page to be parsed and its products extracted
                yield Request(url = brand_url, callback = self.parseBrandPage, meta = {'category' : response.meta['category']})



    # extract each brand page, apply brand filter if option set; send page urls to be further prsed for product urls
    def parseBrandsMenu(self, response):
        hxs = HtmlXPathSelector(response)

        # extract links to brands pages
        brands_links = hxs.select("//ul/li/a")
        for brand_link in brands_links:
            brand_name = brand_link.select("@data-facet-option-value").extract()[0]

            # filter brands if it applies
            if self.brands and not self.name_matches_brands(brand_name):
                self.log("Omitting brand " + brand_name, level=log.INFO)
                continue

            # build brand url
            try:

                # extract brand id
                brand_id = brand_link.select("@data-facet-option-id").extract()[0]
                # extract base url for brand page
                brand_base_url = Utils.add_domain(hxs.select("//form/@action").extract()[0], self.base_url)
                # extract relative url parameters for brand page
                brand_relative_url_params = hxs.select("//input/@value").extract()[0]
                # extract catId parameter
                cat_id_param = re.findall("catId=[0-9]+(?=&|$)", brand_relative_url_params)[0]
                # build brand page
                brand_page_url = brand_base_url + "?" + cat_id_param + "+" + str(brand_id)

                #print brand_page_url

                yield Request(url = brand_page_url, callback = self.parseBrandPage, meta = {'category' : response.meta['category']})

            except Exception, e:
                self.log("Couldn't extract brand page from menu: " + e, level=log.ERROR)


    # parse a brand's page and extract product urls
    def parseBrandPage(self, response):
        hxs = HtmlXPathSelector(response)

        # category of items on this page
        category = response.meta['category']

        # extract item count
        if 'item_count' in response.meta:
            total_item_count = reponse.meta['item_count']
        else:
            total_item_count = int(hxs.select("//p[@id='filtered-products-count']").re("[0-9]+")[0])

        # extract product holder. not extracting <a> element directly because each product holder has many a elements (all just as good, but we only want one)
        product_holders = hxs.select("//div[@class='product ']")
        for product_holder in product_holders:
            # extract first link in product holder
            product_link = product_holder.select(".//a/@href").extract()[0]
            product_url = Utils.add_domain(product_link, self.base_url)

            item = ProductItem()
            item['product_url'] = product_url
            item['category'] = category

            yield item

        # crawl next pages if any left
        if 'offset' not in response.meta:
            offset = 0
        else:
            offset = response.meta['offset']

        next_page = self.build_next_page_url(response.url, total_item_count, offset)

        # if there are more products to crawl, send new request
        if next_page:
            yield Request(url = next_page, callback = self.parseBrandPage, meta = {'offset' : offset + 1, 'total_item_count' : total_item_count, 'category' : category})

    # build next page url, if there are more products to crawl
    def build_next_page_url(self, page, total_item_count, current_offset):
        products_per_page = 20

        # if we parsed all products, return
        if (current_offset + 1) * 20 >= total_item_count:
            return None

        # if there are still products to crawl
        
        # extract query string
        m = re.match("(http://www[^\?&]+)\?([^#]*)", page)
        base_page_url = m.group(1)
        query_string = urllib.unquote(m.group(2)) # this is needed to neutralize the effects of urlencode, otherwise everything will be encoded twice
        # increase value of 'offset' parameter
        parameters_dict = urlparse.parse_qs(query_string) # returns parameters values as lists
        parameters = {p : parameters_dict[p][0] for p in parameters_dict}
        if 'offset' not in parameters:
            # no offset only if offset was 0
            assert current_offset == 0

        parameters['offset'] = (current_offset + 1) * products_per_page
        next_page_url = base_page_url + "?" + urllib.urlencode(parameters)
        return next_page_url




