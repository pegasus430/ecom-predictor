import lxml.html
import itertools
import re

class HsnVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def swatches(self, image_urls):
        swatches = []

        image_color_list = self.tree_html.xpath("//span[@class='inline-image']/text()")

        if image_color_list:
            for image_color in image_color_list:
                for image_url in image_urls:
                    swatch = {
                        'color': image_color,
                        'hero': 1,
                        'hero_image': image_url,
                    }
                    swatches.append(swatch)

        return swatches

    def _variants(self):
        attribute_list = []
        variant_list = []
        color_list = []
        attribute_values_list = []
        size_list_all = []

        color_info = self.tree_html.xpath("//span[@class='inline-image']/text()")
        if color_info:
            for color in color_info:
                color_list.append(color)
        if color_list:
            color_list = [r for r in list(set(color_list)) if len(r.strip()) > 0]
            color_list = [r for r in color_list if r.strip()]
            attribute_values_list.append(color_list)

        size_info = self.tree_html.xpath("//dd[contains(@class, 'matrix-options')]//span/text()")
        if size_info:
            for size in size_info:
                size_list_all.append(size)
        else:
            size_info = self.tree_html.xpath("//dd[@class='tab-panel active small-options clearfix']//label/text()")
            size_list_all = [self._clean_text(size) for size in size_info if self._clean_text(size)]
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

        return variant_list

    def _clean_text(self, text):
        return re.sub("[\r\n\t]", "", text).strip()