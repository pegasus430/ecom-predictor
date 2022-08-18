from search.spiders.search_product_spider import SearchProductSpider
from scrapy.selector import HtmlXPathSelector
from spiders_utils import Utils
from scrapy import log
import re

class EbuyerSpider(SearchProductSpider):

    name = "ebuyer"

    # initialize fields specific to this derived spider
    def init_sub(self):
        self.target_site = "ebuyer"
        self.start_urls = [ "http://www.ebuyer.co.uk" ]

    def extract_results(self, response):
        hxs = HtmlXPathSelector(response)

        results_relative_urls = hxs.select("//h3[@class='listing-product-title']/a/@href").extract()
        results_abs_urls = map(lambda url: "http://www.ebuyer.com" + url, results_relative_urls)

        return results_abs_urls

    def extract_product_data(self, response, item):
        hxs = HtmlXPathSelector(response)

        try:
            item['product_name'] = hxs.xpath("//h1[@class='product-title']/text()").extract()[0]
        except:
            self.log("Error: No product name: " + str(response.url) + " from product: " + item['origin_url'], level=log.INFO)
            # ignore products with no name
            return

        price_node = hxs.select("//p[@class='price']")

        if price_node:

            try:
                price_amount = price_node.select("span[@itemprop='price']/text()").extract()[0]
                price_currency = price_node.select("span[@class='smaller']/text()").extract()[0]
            
                price_amount = re.sub(",","",price_amount)

                m1 = re.match("[0-9]+\.?[0-9]*", price_amount)
                m2 = re.match("(\xa3)|(\$)", price_currency)
                if not m1 or not m2:
                    self.log("Didn't match product price: " + price_amount + price_currency + " " + response.url + "\n", level=log.WARNING)
                else:
                    price = Utils.convert_to_dollars(float(price_amount), price_currency)
                    item['product_target_price'] = price
            except Exception:
                self.log("Didn't find product price: " + response.url + "\n", level=log.INFO)

        try:
            item['product_model'] = hxs.select("//strong[@itemprop='mpn']/text()").extract()[0]
        except Exception:
            pass

        try:
            item['product_brand'] = hxs.select("//div[@itemprop='manufacturer']/meta/@content").extract()[0]
        except Exception:
            pass

        return item



