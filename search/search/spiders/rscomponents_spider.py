from search.spiders.search_results_spider import SearchResultsSpider
from search.items import SearchItem
from scrapy.selector import HtmlXPathSelector
from spiders_utils import Utils
from scrapy import log
import re

class RSComponentsSpider(SearchResultsSpider):

    name = "rscomponents"

    # initialize fields specific to this derived spider
    def init_sub(self):
        self.target_site = "rscomponents"
        self.start_urls = [ "http://uk.rs-online.com" ]

    def extract_result_products(self, response):

        hxs = HtmlXPathSelector(response)

        results = hxs.select("//tr[@class='resultRow']")
        items = []


        for result in results:

            item = SearchItem()
            product_name = result.select("td[@class='descColHeader']//a[not(starts-with(text(), 'See similar'))]/text()").extract()
            product_url = result.select("td[@class='descColHeader']//a[not(starts-with(text(), 'See similar'))]/@href").extract()

            # for category-specific search result pages
            if not product_name:
                product_name = result.select("td[@class='fixedCell']//" + \
                    "a[not(starts-with(text(), 'See similar') or starts-with(text(), 'Quick View')" + \
                    " or starts-with(text(), 'Check stock'))]/text()").extract()
                product_url = result.select("td[@class='fixedCell']//" + \
                    "a[not(starts-with(text(), 'See similar')" + \
                    " or starts-with(text(), 'Quick View') or starts-with(text(), 'Check stock'))]/@href").extract()

            # quit if there is no product name
            if product_name and product_url:
                item['product_url'] = "http://uk.rs-online.com" + product_url[0].strip()
                item['product_name'] = product_name[0].strip()
            else:
                self.log("No product name: " + str(response.url) + " from product: " + response.meta['origin_url'], level=log.ERROR)
                continue

            # extract price
            price_holder = result.select(".//span[@class='price right5']/text()").extract()

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
            try:
                item['product_brand'] = result.select(".//div[@class='partColContent']//li[starts-with('Brand', .//text())]/a/text()").\
                                            extract()[0].strip()
            except Exception:
                pass

            # extract product model
            try:
                item['product_model'] = result.select(".//div[@class='partColContent']//li[starts-with('Mfr. Part No.', .//text())]" + \
                    "/span[@class='defaultSearchText']/text()").extract()[0].strip()
            except Exception:
                self.log("Didn't find product model: " + response.url + "\n", level=log.DEBUG)

            items.append(item)

        return items


