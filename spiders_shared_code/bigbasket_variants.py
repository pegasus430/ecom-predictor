
import re
import lxml.html

from lxml import html, etree


class BigbasketVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self):
        skus = self.tree_html.xpath("//div[@itemtype='http://schema.org/Product']//div[@class='uiv2-size-variants']//input[@type='radio']/@value")
        images = self.tree_html.xpath("//div[@class='uiv2-product-large-img-container']//img/@data-src")
        sizes = self.tree_html.xpath("//div[@itemtype='http://schema.org/Product']//div[@class='uiv2-size-variants']//label/text()")

        attribute_list = []
        variant_list = []
        image_list = []
        attribute_values_list = []
        size_list_all = []

        for image in images:
            image = 'https:' + image
            image_list.append(image)
        if image_list:
            image_list = [r for r in list(set(image_list)) if len(r.strip()) > 0]
            attribute_values_list.append(image_list)
        for size in sizes:
            size = self._clean_text(size).replace(' ', '')
            size_list_all.append(size)
        if size_list_all:
            size_list_all = [r for r in list(set(size_list_all)) if len(r.strip()) > 0]
            attribute_values_list.append(size_list_all)

        if image_list:
            if 'image' not in attribute_list:
                attribute_list.append('image')
        if size_list_all:
            if 'size' not in attribute_list:
                attribute_list.append('size')

        for reindex, sku in enumerate(skus):
            variant_item = {}
            properties = {}
            for index, attribute in enumerate(attribute_list):
                properties[attribute] = attribute_values_list[index][reindex]
            variant_item['properties'] = properties

            variant_item['sku'] = sku
            variant_list.append(variant_item)

        if variant_list:
            return variant_list

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t]", "", text).strip()
