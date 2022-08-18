
import re
import lxml.html

from lxml import html, etree


class BarnesandnobleVariants(object):

    IMAGE_URL = 'http://prodimage.images-bn.com/pimages/{sku}_p0_v0_s1200x630.jpg'

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self):
        sizes = []
        prices = []
        skus = []
        images = []
        size_info = self.tree_html.xpath("//select[@id='otherAvailFormats']//option/text()")
        sku_info = self.tree_html.xpath("//select[@id='otherAvailFormats']//option/@value")

        for vrt in size_info:
            sizes.append(vrt.split('-')[0].strip())
            prices.append(vrt.split('-')[1].strip())

        for vrt in sku_info:
            try:
                sku = re.search('ean=(\d+)', vrt).group(1)
            except:
                pass
            skus.append(sku)
            images.append(self.IMAGE_URL.format(sku=sku))

        attribute_list = []
        variant_list = []
        attribute_values_list = []

        if images:
            attribute_values_list.append(images)
        if sizes:
            sizes = [r for r in list(set(sizes)) if len(r.strip()) > 0]
            attribute_values_list.append(sizes)
        if prices:
            attribute_values_list.append(prices)

        if images:
            if 'image' not in attribute_list:
                attribute_list.append('image')
        if sizes:
            if 'size' not in attribute_list:
                attribute_list.append('size')
        if prices:
            if 'price' not in attribute_list:
                attribute_list.append('price')

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
