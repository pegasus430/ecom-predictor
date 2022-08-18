from search.spiders.search_product_spider import SearchProductSpider
from scrapy.selector import HtmlXPathSelector
from spiders_utils import Utils
from scrapy import log
import re

class ScrewfixSpider(SearchProductSpider):

    name = "screwfix"

    # initialize fields specific to this derived spider
    def init_sub(self):
        self.target_site = "screwfix"
        self.start_urls = [ "http://screwfix.com" ]

    def extract_results(self, response):
        hxs = HtmlXPathSelector(response)

        results_urls = hxs.select("//div[@class='pad']/a/@href").extract()

        return results_urls

    def extract_product_data(self, response, item):
        hxs = HtmlXPathSelector(response)

        try:
            item['product_name'] = hxs.xpath("//h1[@itemprop='name']/text()").extract()[0]
        except:
            self.log("Error: No product name: " + str(response.url) + " from product: " + item['origin_url'], level=log.INFO)
            # ignore products with no name
            return

        try:
            price = hxs.select("//p[@class='price']/span[@itemprop='price']/text()").extract()[0]
            price = re.sub(",","",price)

            m = re.match("(\xa3|\$)([0-9]+\.?[0-9]*)", price)
            if not m:
                self.log("Didn't match product price: " + price_amount + price_currency + " " + response.url + "\n", level=log.WARNING)
            else:
                price_amount = m.group(2)
                price_currency = m.group(1)
                price_value = Utils.convert_to_dollars(float(price_amount), price_currency)
                item['product_target_price'] = price_value
        except Exception:
            self.log("Didn't find product price: " + response.url + "\n", level=log.INFO)

        try:
            item['product_model'] = hxs.select("//div[@id='product_additional_details_container']" + \
                "//tr[starts-with(.//text()[normalize-space()], 'Model')]/td/text()")\
            .extract()[0].strip()
        except Exception:
            pass

        try:
            item['product_brand'] = hxs.select("//div[@id='product_additional_details_container']" + \
                "//tr[starts-with(.//text()[normalize-space()], 'Brand')]/td/text()")\
            .extract()[0].strip()
        except Exception:
            pass

        return item



