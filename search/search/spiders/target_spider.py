from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from scrapy.http import TextResponse
from scrapy.http import Response
from scrapy.exceptions import CloseSpider
from search.items import SearchItem
from search.spiders.search_spider import SearchSpider
from search.spiders.search_product_spider import SearchProductSpider
from scrapy import log

from spiders_utils import Utils
from search.matching_utils import ProcessText

import re
import sys


class TargetSpider(SearchProductSpider):

    name = "target"

    # initialize fields specific to this derived spider
    def init_sub(self):
        self.target_site = "target"
        self.start_urls = [ "http://www.target.com" ]

    def extract_results(self, response):
        hxs = HtmlXPathSelector(response)

        results = hxs.select("//li[contains(@class,'tile standard')]")
        results_urls = []
        for result in results:
            product_title_holder = result.select(".//div[@class='tileInfo']/a[contains(@class,'productTitle')]")

            # try again, xpath for second type of page structure (ex http://www.target.com/c/quilts-bedding-home/-/N-5xtuw)
            if not product_title_holder:
                product_title_holder = result.select(".//div[@class='tileInfo']//*[contains(@class,'productTitle')]/a")

            product_url_node = product_title_holder.select("@href").extract()

            # quit if there is no product name
            if product_url_node:
                # clean url
                m = re.match("(.*)#prodSlot*", product_url_node[0])
                if m:
                    product_url = m.group(1)
                else:
                    product_url = product_url_node[0]
                results_urls.append(product_url)

        return results_urls

    def extract_product_data(self, response, item):
        hxs = HtmlXPathSelector(response)

        #TODO: is this general enough?
        product_name = hxs.select("//h2[@class='product-name item']/span[@itemprop='name']/text()").extract()

        # if you can't find product name in product page, use the one extracted from results page
        if not product_name:
            # item['product_name'] = response.meta['product_name']
            self.log("Error: product name not found on product page: " + str(response.url), level=log.INFO)
        else:
            item['product_name'] = product_name[0].strip()

        if 'product_name' not in item or not item['product_name']:
            self.log("Error: No product name: " + str(response.url), level=log.INFO)

        else:
            # consider DPCI as model number
            # TODO: not sure if the best approach, maybe in the future add separate field "DPCI"
            # TODO: may make things worse where there is also an actual model number in the name?
            
            DPCI_holder =  hxs.select("//li[contains(strong/text(), 'DPCI')]/text()").re("[0-9\-]+")
            # try hidden tag
            if not DPCI_holder:
                DPCI_holder = hxs.select("//input[@id='dpciHidden']/@value").extract()

            if DPCI_holder:
                item['product_upc'] = [DPCI_holder[0].strip()]
            # if no product model explicitly on the page, try to extract it from name
            
            # no model to extract directly from page for target            
            product_model_extracted = ProcessText.extract_model_from_name(item['product_name'])
            if product_model_extracted:
                item['product_model'] = product_model_extracted
            #print "MODEL EXTRACTED: ", product_model_extracted, " FROM NAME ", item['product_name'].encode("utf-8")


            #TODO: no brand field?

            # extract price
            #! extracting list price and not discount price when discounts available?
            #TODO: complete this with other types of pages
            price_holder = hxs.select("//span[@class='offerPrice']/text()").extract()

            if price_holder:
                product_target_price = price_holder[0].strip()
                # remove commas separating orders of magnitude (ex 2,000)
                product_target_price = re.sub(",","",product_target_price)
                m = re.match("\$([0-9]+\.?[0-9]*)", product_target_price)
                if m:
                    item['product_target_price'] = float(m.group(1))
                else:
                    sys.stderr.write("Didn't match product price: " + product_target_price + " " + response.url + "\n")

            else:
                sys.stderr.write("Didn't find product price: " + response.url + "\n")


            return item
