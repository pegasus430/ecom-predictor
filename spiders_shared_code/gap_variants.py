from lxml import html
import itertools


class GapVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = html.fromstring(response.body)

    def setupCH(self, tree_html, product_json):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.product_json = product_json

    def swatches(self, image_urls):
        swatches = []
        image_color_list = []

        if self.color_info:
            for color in self.color_info:
                image_color_list.append(color['colorName'])

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
        alt_variant_info = None
        self.color_info = None
        size_info = None
        attribute_list = []
        variant_list = []
        color_list = []
        attribute_values_list = []
        size_list_all = []

        keywords = self.tree_html.xpath("//meta[@name='keywords']/@content")[0]
        variants_info = self.product_json['variants']
        for variants in variants_info:
            if variants['name'] in keywords:
                alt_variant_info = variants

        if not alt_variant_info:
            alt_variant_info = variants_info[0]

        if alt_variant_info:
            if alt_variant_info.get('productStyleColors', {}):
                self.color_info = alt_variant_info['productStyleColors'][0]
            if alt_variant_info.get('sizeDimensions', {}):
                size_info = alt_variant_info['sizeDimensions']['sizeDimension1']['dimensions']

        if self.color_info:
            for color in self.color_info:
                color_list.append(color['colorName'])
        if color_list:
            color_list = [r for r in list(set(color_list)) if len(r.strip()) > 0]
            attribute_values_list.append(color_list)

        if size_info:
            for size in size_info:
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
