from search.spiders.search_results_spider import SearchResultsSpider
from search.items import SearchItem
from scrapy.selector import HtmlXPathSelector
from spiders_utils import Utils
from scrapy import log
import re

class ArgosSpider(SearchResultsSpider):

    name = "argos"

    # initialize fields specific to this derived spider
    def init_sub(self):
        self.target_site = "argos"
        self.start_urls = [ "http://www.argos.co.uk" ]

    def extract_result_products(self, response):

        hxs = HtmlXPathSelector(response)

        results = hxs.select("//li[starts-with(@class, 'item')]/dl")
        items = []

        for result in results:

            item = SearchItem()
            product_name = result.select("dt[@class='title']/a/text()").extract()
            product_url = result.select("dt[@class='title']/a/@href").extract()

            # quit if there is no product name
            if product_name and product_url:
                item['product_url'] = product_url[0]
                item['product_name'] = product_name[0]
            else:
                self.log("No product name: " + str(response.url) + " from product: " + response.meta['origin_url'], level=log.ERROR)
                continue

            # extract price
            #! extracting regular price and not discount price when discounts available?
            price_holder = result.select("dd[@class='price']/span/text()").extract()

            if price_holder:
                product_target_price = price_holder[0].strip()
                # remove commas separating orders of magnitude (ex 2,000)
                product_target_price = re.sub(",","",product_target_price)
                # if more than one match, it will get the first one
                m = re.match("(\xa3)([0-9]+\.?[0-9]*)", product_target_price)
                if m:
                    price = float(m.group(2))
                    currency = m.group(1)
                    item['product_target_price'] = Utils.convert_to_dollars(price, currency)
                else:
                    self.log("Didn't match product price: " + product_target_price + " " + response.url + "\n", level=log.WARNING)

            else:
                self.log("Didn't find product price: " + response.url + "\n", level=log.DEBUG)

            # extract product brand
            #

            items.append(item)

        return items


