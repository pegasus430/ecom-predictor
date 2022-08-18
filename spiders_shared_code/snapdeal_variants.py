import json

import lxml.html


class SnapdealVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self):
        variant_json = json.loads(self.tree_html.xpath("//div[@id='attributesJson']")[0].text_content().strip())

        if not variant_json:
            return None

        price_amount = self.tree_html.xpath("//input[@id='productPrice']/@value")[0]

        if str(int(price_amount)) == price_amount:
            price_amount = int(price_amount)
        else:
            price_amount = float(price_amount)

        variant_list = []

        for variant_item in variant_json:
            variant = {}
            properties = {}
            properties[variant_item["name"].lower()] = variant_item["value"]
            in_stock = not variant_item["soldOut"]
            variant["price"] = price_amount
            variant["in_stock"] = in_stock
            variant["properties"] = properties
            variant["url"] = None
            variant["selected"] = False
            variant["image_url"] = "http://n3.sdlcdn.com/" + variant_item["images"][0]
            variant_list.append(variant)

        if not variant_list:
            return None

        return variant_list
