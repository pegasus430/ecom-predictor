import lxml.html
import itertools

class FootlockerVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self, model_json, image_urls):
        attribute_list = []
        variant_list = []
        attribute_values_list = []
        size_list_all = []

        if image_urls:
            image_urls = [r for r in list(set(image_urls)) if len(r.strip()) > 0]
            attribute_values_list.append(image_urls)

        size_info = model_json['AVAILABLE_SIZES']
        if size_info:
            for size in size_info:
                size_list_all.append(size)
        if size_list_all:
            size_list_all = [r for r in list(set(size_list_all)) if len(r.strip()) > 0]
            attribute_values_list.append(size_list_all)

        combination_list = list(itertools.product(*attribute_values_list))
        combination_list = [list(tup) for tup in combination_list]
        if image_urls:
            if 'image' not in attribute_list:
                attribute_list.append('image')
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