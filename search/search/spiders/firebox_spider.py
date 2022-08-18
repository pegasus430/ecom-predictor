from search.spiders.search_product_spider import SearchProductSpider
from scrapy.selector import HtmlXPathSelector
from spiders_utils import Utils
from scrapy import log
import re

class FireboxSpider(SearchProductSpider):

    name = "firebox"

    # initialize fields specific to this derived spider
    def init_sub(self):
        self.target_site = "firebox"
        self.start_urls = [ "http://www.firebox.com" ]

    def extract_results(self, response):
        hxs = HtmlXPathSelector(response)

        # reject page if no results were found
        # (in which case firebox will return a page with new products on their site)
        try:
            res_title = hxs.select("//div[@class='searchtitle']/text()").extract()[0]
            if "No results were found for" in res_title:
                return []
        except Exception:
            pass

        results_relative_urls = hxs.select("//div[@class='block']//a[@class='block_gradient_link']/@href").extract()
        results_abs_urls = map(lambda url: "http://www.firebox.com" + url, results_relative_urls)

        return results_abs_urls

    def extract_product_data(self, response, item):
        hxs = HtmlXPathSelector(response)

        try:
            item['product_name'] = hxs.select("//h2[@class='product_name product_title']/span[@itemprop='name']/text()").extract()[0]
        except:
            self.log("Error: No product name: " + str(response.url) + " from product: " + item['origin_url'], level=log.INFO)
            # ignore products with no name
            return

        price = hxs.select("//div[@class='price']/text() | //div[@class='pricestring']/text()").extract()[0].strip()

        if price.startswith("from "):
            price = price[5:].strip()

        m = re.match("(\xa3|\$)([0-9]+\.?[0-9]*)", price)
        if not m:
            self.log("Didn't match product price: " + price + " " + response.url + "\n", level=log.WARNING)
        else:
            price_amount = m.group(2)
            price_currency = m.group(1)
            price_value = Utils.convert_to_dollars(float(price_amount), price_currency)
            item['product_target_price'] = price_value

        return item



