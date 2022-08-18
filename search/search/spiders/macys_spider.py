from search.spiders.search_results_spider import SearchResultsSpider
from search.items import SearchItem
from scrapy.selector import HtmlXPathSelector
from spiders_utils import Utils
from scrapy import log
import re

class MacysSpider(SearchResultsSpider):

    name = "macys"

    # initialize fields specific to this derived spider
    def init_sub(self):
        self.target_site = "macys"
        self.start_urls = [ "http://www1.macys.com/" ]

    def extract_result_products(self, response):

        hxs = HtmlXPathSelector(response)

        results = hxs.select("//div[@class='innerWrapper']")
        items = []

        for result in results:

            item = SearchItem()
            product_name = result.select(".//div[@class='shortDescription']/a/text()").extract()
            product_url = result.select(".//div[@class='shortDescription']/a/@href").extract()

            # quit if there is no product name
            if product_name and product_url:
                item['product_url'] = "http://www1.macys.com" + product_url[0]
                item['product_name'] = product_name[0].strip()
            else:
                self.log("No product name: " + str(response.url) + " from product: " + response.meta['origin_url'], level=log.ERROR)
                continue

            # extract price
            #! extracting regular price and not discount price when discounts available?
            price_holder = result.select("div[@class='prices']/span/text()").extract()

            if price_holder:
                product_target_price = price_holder[0].strip()
                # remove commas separating orders of magnitude (ex 2,000)
                product_target_price = re.sub(",","",product_target_price)
                # if more than one match, it will get the first one
                m = re.match("([a-zA-Z\.\s]+)?(\xa3|\$)([0-9]+\.?[0-9]*)", product_target_price)
                if m:
                    price = float(m.group(3))
                    currency = m.group(2)
                    item['product_target_price'] = Utils.convert_to_dollars(price, currency)
                else:
                    self.log("Didn't match product price: " + product_target_price + " " + response.url + "\n", level=log.WARNING)

            else:
                self.log("Didn't find product price: " + response.url + "\n", level=log.DEBUG)

            # extract product brand
            #

            items.append(item)

        return items


