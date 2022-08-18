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

class EbaySpider(SearchProductSpider):

    name = "ebay"

    # initialize fields specific to this derived spider
    def init_sub(self):
        self.target_site = "ebay"
        self.start_urls = [ "http://www.ebay.com" ]

    def extract_results(self, response):
        hxs = HtmlXPathSelector(response)
        product_urls = []

        results = hxs.select("//div[@id='ResultSetItems']//h3/a | //div[@id='PaginationAndExpansionsContainer']//h3/a")
        for result in results:
            product_url = result.select("@href").extract()[0]

            product_urls.append(product_url)


        return product_urls

    def extract_product_data(self, response, item):
        hxs = HtmlXPathSelector(response)
        
        # extract product name
        product_name = hxs.select("//h1[@id='itemTitle']/text()").extract()
        if not product_name:
            self.log("Error: No product name: " + str(response.url), level=log.INFO)

        else:

            item['product_name'] = product_name[0]

            # extract product brand
            product_brand_holder = hxs.select("//td[@class='attrLabels'][contains(normalize-space(),'Brand')]" + \
                "/following-sibling::node()[normalize-space()!=''][1]//text()[normalize-space()!='']").extract()
            if product_brand_holder:
                item['product_brand'] = product_brand_holder[0]

            # extract product model
            product_model_holder = hxs.select("//td[@class='attrLabels'][contains(normalize-space(),'Model')]" + \
                "/following-sibling::node()[normalize-space()!=''][1]//text()[normalize-space()!='']").extract()
            if not product_model_holder:
                product_model_holder = hxs.select("//td[@class='attrLabels'][contains(normalize-space(),'MPN')]" + \
                "/following-sibling::node()[normalize-space()!=''][1]//text()[normalize-space()!='']").extract()

            if product_model_holder:
                item['product_model'] = product_model_holder[0]

            # TODO: upc?
            
            price_holder = hxs.select("//span[@itemprop='price']/text() | //span[@id='mm-saleDscPrc']/text()")
            try:
                (currency, price) = price_holder.re("(\$|\xa3)([0-9\.]+)")
                if currency != "$":
                    price = Utils.convert_to_dollars(float(price), currency)
                item['product_target_price'] = float(price)
            except:
                self.log("No price: " + str(response.url), level=log.WARNING)


            return item
