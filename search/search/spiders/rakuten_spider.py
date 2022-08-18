from search.spiders.search_product_spider import SearchProductSpider
from scrapy.selector import HtmlXPathSelector
from spiders_utils import Utils
from scrapy import log
import re

class RakutenSpider(SearchProductSpider):

    name = "rakuten"

    # initialize fields specific to this derived spider
    def init_sub(self):
        self.target_site = "rakuten"
        self.start_urls = [ "http://www.rakuten.co.uk" ]

    def extract_results(self, response):
        hxs = HtmlXPathSelector(response)

        results_relative_urls = hxs.select("//li[@class='b-item']//div[@class='b-text']//b/a/@href").extract()
        results_abs_urls = map(lambda url: "http://www.rakuten.co.uk" + url, results_relative_urls)

        return results_abs_urls

    def extract_product_data(self, response, item):
        hxs = HtmlXPathSelector(response)

        try:
            item['product_name'] = hxs.xpath("//h1[@class='b-ttl-main']/text()").extract()[0]
        except:
            self.log("Error: No product name: " + str(response.url) + " from product: " + item['origin_url'], level=log.INFO)
            # ignore products with no name
            return

        try:
            price_amount = hxs.select("//meta[@itemprop='price']/@content").extract()[0]
            price_currency = hxs.select("//meta[@itemprop='priceCurrency']/@content").extract()[0]
        
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
            item['product_model'] = hxs.select("//input[@class='sku']/@value").extract()[0]
        except Exception:
            pass

        try:
            item['product_brand'] = hxs.select("//span[@itemprop='brand']/text()").extract()[0]
        except Exception:
            pass

        return item



