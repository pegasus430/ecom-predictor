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
# scrapy crawl ocado -a cat_page="<url>" [-a outfile="<filename>" -a brands_file="<brands_filename>"]
# 
# (if specified, brands_filename contains list of brands that should be considered - one brand on each line. other brands will be ignored)
#
################################


class OcadoSpider(CaturlsSpider):

    name = "ocado"
    allowed_domains = ["ocado.com"]

    # ocado haircare
    #self.start_urls = ["http://www.ocado.com/webshop/getCategories.do?tags=%7C20000%7C21584%7C21585"]

    # add brand option
    def __init__(self, cat_page, outfile = "product_urls.csv", use_proxy = False, brands_file=None):
        super(OcadoSpider, self).__init__(cat_page=cat_page, outfile=outfile, use_proxy=use_proxy)

        self.base_url = "http://www.ocado.com"

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

    # extract category pages and send them to be further parsed
    def parse(self, response):
        hxs = HtmlXPathSelector(response)

        categories_links = hxs.select("//div[@class='nav baseLevel']/ul/li/a")
        for category_link in categories_links:
            category_name = category_link.select("text()").extract()[0]
            category_url = Utils.add_domain(category_link.select("@href").extract()[0], self.base_url)

            # if brand filter is set, send to parseCategory to extract brands pages from menu
            if self.brands:
                yield Request(url = category_url, callback = self.parseCategory, meta = {'category' : category_name})
            # if we're extracting all brands, send it directly to extract products from it
            else:
                yield Request(url = category_url, callback = self.parseBrand, meta = {'category' : category_name})

    # from category pages: extract urls to brands pages, apply brand filter if option set; send page urls to be further prsed for product urls
    def parseCategory(self, response):
        hxs = HtmlXPathSelector(response)

        brands_links = hxs.select("//li[contains(@class,'brandsSel')]/a")
        for brand_link in brands_links:
            brand_name = brand_link.select("text()[normalize-space()]").extract()[0].strip()
            brand_url = Utils.add_domain(brand_link.select("@href").extract()[0], self.base_url)

            # filter brand if brand filter set
            if self.brands and not self.name_matches_brands(brand_name):
                self.log("Omitting brand " + brand_name, level=log.INFO)
                continue

            # crawl brand page if it passed filter
            yield Request(url = brand_url, callback = self.parseBrand, meta = {'category' : response.meta['category']})

    # build url for next page (add page parameter)
    # return only if there is a next page (we haven't crawled all products)
    # first flag set to True if this is the first page (probably no page parameter in the url)
    def build_next_page_url(self, page_url, total_product_count, current_product_count, first=True):

        # if we reached the maximum number of products, don't try to crawl the next page
        if current_product_count >= total_product_count:
            return None

        m = re.match("(http://www.*&index=)([0-9]+)", page_url)
        # if I can't extract the current page, it must be the first
        if not m:
            assert first
            current_page_nr = 0
            # this was the first page so we must add the page parameter for the second page to the received url
            next_page_url = page_url + "&index=" + str(current_page_nr + 1)

            return next_page_url

        else:
            current_page_nr = int(m.group(2))
            # replace old page number by new page number
            next_page_url = m.group(1) + str(current_page_nr + 1)

            # test if current product count is what we would expect given the page number
            products_per_page = 20
            assert current_product_count == ((current_page_nr + 1) * products_per_page)

            return next_page_url


    def parseBrand(self, response):
        hxs = HtmlXPathSelector(response)

        # category of items on current page
        category = response.meta['category']

        # set parameters in meta specifying current product count and total product count for this brand
        # to be used for deciding on stop criteria on pagination
        if 'total_product_count' in response.meta:
            product_count = response.meta['total_product_count']
            cur_product_count = response.meta['current_product_count']
        else:
            # extract number of products for this brand
            product_count = int(hxs.select("//h2[@id='productCount']//text()").re("[0-9]+")[0])
            cur_product_count = 0

        # extract products from this page
        product_links = hxs.select("//h3[@class='productTitle']/a/@href").extract()
        # add domain
        product_urls = map(lambda x: Utils.add_domain(x, self.base_url), product_links)

        for product_url in product_urls:
            item = ProductItem()
            # remove parameters in url
            item['product_url'] = Utils.clean_url(product_url)
            item['category'] = category

            yield item

        # add nr of extracted products to current product count
        cur_product_count += len(product_urls)

        # get next page if any
        next_page = self.build_next_page_url(response.url, product_count, cur_product_count, first=('total_product_count' not in response.meta))

        if next_page:
            yield Request(url = next_page, callback = self.parseBrand, meta = {'total_product_count' : product_count, 'current_product_count' : cur_product_count, 'category' : category})

        
