import lxml.html
import itertools
import re

class WilliamssonomaVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self):
        attribute_list = []
        variant_list = []
        attribute_values_list = []

        variants_title = self.tree_html.xpath("//section[@class='simple-subset']//div[@class='subset-attributes']//h4/text()")
        single_attribute_list = self.tree_html.xpath("//section[@class='simple-subset']//li[@class='attributeValue']//a/@title")
        variant_list_all = [self._clean_text(attr) for attr in single_attribute_list if len(attr) > 0]
        if not variant_list_all:
            single_attribute_list = self.tree_html.xpath("//section[@class='simple-subset']//li[@class='attributeValue']//a/text()")
        variant_list_all = [self._clean_text(attr) for attr in single_attribute_list if len(attr) > 0]
        attribute_values_list.append(variant_list_all)

        combination_list = list(itertools.product(*attribute_values_list))
        combination_list = [list(tup) for tup in combination_list]

        if single_attribute_list and variants_title:
            if 'select color' in variants_title[0].lower():
                attribute_list.append('color')
            if 'select size' in variants_title[0].lower():
                attribute_list.append('size')

        for variant_combination in combination_list:
            variant_item = {}
            properties = {}
            for index, attribute in enumerate(attribute_list):
                properties[attribute] = variant_combination[index]
            variant_item['properties'] = properties
            variant_list.append(variant_item)

        return variant_list

    def _clean_text(self, text):
        return re.sub("[\r\n\t]", "", text).strip()