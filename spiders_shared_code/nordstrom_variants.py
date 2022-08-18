import itertools

class NordStromVariants(object):

    def setupSC(self, product_json):
        """ Call it from SC spiders """
        self.product_json = product_json

    def setupCH(self, product_json):
        """ Call it from CH spiders """
        self.product_json = product_json

    def _variants(self):
        variant_list = []

        for choice in self.product_json.get('Model', {}).get('StyleModel', {}).get('ChoiceGroups', []):
            attribute_values_list = []
            color_list = []
            size_list = []
            attribute_list = []
            group = choice.get('ChoiceGroupName')
            if choice.get('Size'):
                for size in choice.get('Size', []):
                    if size.get('IsAvailable'):
                        size_list.append(size.get('Value'))

            if choice.get('Color'):
                for color in choice.get('Color', []):
                    if color.get('IsAvailable'):
                        color_list.append(color.get('DisplayValue'))

            if size_list:
                attribute_list.append('SizeId')
                attribute_values_list.append(size_list)

            if color_list:
                attribute_list.append('ColorName')
                attribute_values_list.append(color_list)

            combination_list = list(itertools.product(*attribute_values_list))
            combination_list = [list(tup) for tup in combination_list]
            for variant_combination in combination_list:
                variant_item = {}
                properties = {}
                properties['Filter'] = group
                for index, attribute in enumerate(attribute_list):
                    properties[attribute] = variant_combination[index]
                variant_item['properties'] = properties
                variant_list.append(variant_item)

            if 'Filter' not in attribute_list:
                attribute_list.append('Filter')

            for variant in variant_list:
                variant['in_stock'] = False
                for sku in self.product_json.get('Model', {}).get('StyleModel', {}).get('Skus', []):
                    in_stock = True
                    for attribute in attribute_list:
                        in_stock = in_stock and sku[attribute] == variant['properties'][attribute]

                    if in_stock:
                        variant['in_stock'] = True
                        break

        return variant_list