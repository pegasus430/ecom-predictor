import lxml.html
import json


class NikeVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _find_between(self, s, first, last):
        try:
            start = s.index(first) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""

    def _variants(self):
        try:
            product_json_text = self.tree_html.xpath(
                "//script[@id='product-data']/text()")[0]
            product_json = json.loads(product_json_text)
        except Exception as _:
            product_json = None

        variant_list = []

        if product_json["inStockColorways"]:
            for swatch in product_json["inStockColorways"]:
                variant_item = {}
                properties = {"color": swatch["colorDescription"]}
                variant_item["properties"] = properties
                variant_item["price"] = float(self.tree_html.xpath(
                    "//meta[@property='og:price:amount']/@content")[0])
                variant_item["in_stock"] = True \
                    if swatch["status"] == "IN_STOCK" else False
                variant_item["url"] = swatch["url"]
                variant_item["selected"] = True \
                    if "pid-" + str(product_json["productId"]) \
                    in swatch["url"] else False
                variant_list.append(variant_item)

        if variant_list:
            return variant_list

        return None
