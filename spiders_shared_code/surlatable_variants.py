from lxml import html
import re

class SurlatableVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self, price):
        attribute_list = []
        variant_list = []
        properties_info = self.tree_html.xpath("//div[@class='product-optionsColor-select']| "
                                               "//div[@class='product-optionsSize-select']")
        skus = [p.xpath(".//a/@data-sku") for p in properties_info if len(properties_info) > 0]
        if properties_info:
            attribute_values_list = properties_info[0].xpath(".//a/text()")
            skus = properties_info[0].xpath(".//a/@data-sku")
        if properties_info:
            if 'data-size' in html.tostring(properties_info[0]) and 'size' not in attribute_list:
                attribute_list.append('size')
            if 'data-color' in html.tostring(properties_info[0]) and 'color' not in attribute_list:
                attribute_list.append('color')
        if skus and attribute_list:
            for index, attr in enumerate(attribute_values_list):
                sku_txt = re.search(r'%s:\ {(.*?)},' % skus[index], html.tostring(self.tree_html), re.DOTALL)
                if sku_txt:
                    sku_txt = sku_txt.group(1)
                    variant_price = re.search(r'markdownPrice: \"(\d*\.\d+|\d+)\",', sku_txt, re.DOTALL)
                    if not variant_price:
                        variant_price = re.search(r'basePrice: \"(\d*\.\d+|\d+)\",', sku_txt, re.DOTALL)
                    if variant_price:
                        price = float(variant_price.group(1))

                variant_item = {
                    'properties': {
                        attribute_list[0]: attr
                    },
                    'sku_id': skus[index],
                    'price': price,
                }
                variant_list.append(variant_item)

        return variant_list