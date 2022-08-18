
import re
import lxml.html
import itertools

from lxml import html, etree


class BedBathAndBeyondVariants(object):

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
        size_list_all = []
        color_list = []

        colors = self._get_colors()
        for color in colors:
            color_list.append(color)
        if color_list:
            color_list = [r for r in list(set(color_list)) if len(r.strip()) > 0]
            attribute_values_list.append(color_list)

        sizes = self._get_sizes()
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
        return variant_list

    def _swatches(self):
        swatch_list = []
        image_list = []
        colors = self._get_colors()
        images = self._get_images()

        for image in images:
            image = 'https:' + image.split('?')[0] + '?hei=500&wid=500&qlt=50,1'
            image_list.append(image)

        for index, color in enumerate(colors):
            swatch_info = {}
            swatch_info["color"] = color
            swatch_info["image"] = image_list[index]
            swatch_list.append(swatch_info)

        if swatch_list:
            return swatch_list

        return None

    def _get_sizes(self):
        sizes = self.tree_html.xpath(
            "//select[@id='selectProductSize']"
            "//option/text()")

        return sizes[1:]

    def _get_colors(self):
        colors = self.tree_html.xpath(
            "//ul[contains(@class, 'swatches')]"
            "//li[contains(@class, 'colorSwatchLi')]/@title")

        return colors

    def _get_images(self):
        images = self.tree_html.xpath(
            "//ul[contains(@class, 'swatches')]"
            "//li[contains(@class, 'colorSwatchLi')]/@data-imgurlthumb")

        return images

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t]", "", text).strip()
