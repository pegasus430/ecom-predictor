# ~~coding=utf-8~~
from __future__ import division, absolute_import, unicode_literals

import re
import lxml.html
import itertools


class ModClothVariants(object):

    def setupSC(self, response, product_url=None):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = lxml.html.fromstring(response.body)
        self.product_url = product_url

    def setupCH(self, tree_html, product_url=None):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.product_url = product_url

    def _variants(self):
        attribute_list = []
        variant_list = []
        attribute_values_list = []
        size_list_all = []
        color_list = []
        selected = False
        in_stock = 0

        colors = self.tree_html.xpath('//div[contains(@class, "product-variations")]/ul/li[1]//img/@alt')
        for color in colors:
            color_list.append(color)
        if color_list:
            color_list = [r for r in list(set(color_list)) if len(r.strip()) > 0]
            attribute_values_list.append(color_list)

        sizes = self.tree_html.xpath('//div[contains(@class, "product-variations")]/ul/li[2]//text()')
        sizes = [el.replace('\n', '') for el in sizes]
        sizes = [size for size in sizes if size != '']

        for size in sizes:
            size = self._clean_text(size).replace(' ', '')
            size_list_all.append(size)
        if size_list_all:
            size_list_all = [r for r in list(set(size_list_all)) if len(r.strip()) > 0]
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

        if len(variant_list) > 1:
            return variant_list

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\r\n\t]", "", text).strip()