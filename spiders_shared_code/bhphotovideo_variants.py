import lxml.html
import itertools
import re

class BhphotovideoVariants(object):

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
        color_list = []
        attribute_values_list = []
        size_list_all = []

        color_info = self.tree_html.xpath('//div[contains(@class, "fs14 tag clearfix")]/a/@data-itemvalue')
        if color_info:
            for color in color_info:
                color_list.append(color)
        if color_list:
            color_list = [r for r in list(set(color_list)) if len(r.strip()) > 0]
            color_list = [r for r in color_list if r.strip()]
            attribute_values_list.append(color_list)

        size_info = self.tree_html.xpath('//a[contains(@class, "group-item js-groupItem c28 noUnderline")]/text()')
        if size_info:
            for size in size_info:
                size_list_all.append(self._clean_text(size))
        if size_list_all:
            size_list_all = [r for r in list(set(size_list_all)) if len(r.strip()) > 0]
            size_list_all = [r for r in size_list_all if r.strip()]
            attribute_values_list.append(size_list_all)

        combination_list = list(itertools.product(*attribute_values_list))
        combination_list = [list(tup) for tup in combination_list]

        if color_list:
            if 'color' not in attribute_list:
                attribute_list.append('color')
        if size_list_all:
            if 'size' not in attribute_list:
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