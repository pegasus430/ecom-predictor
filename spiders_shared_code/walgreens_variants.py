import lxml.html
import copy


class WalgreensVariants(object):

    def setupSC(self, inventory):
        """ Call it from SC spiders """
        self.inventory = inventory

    def setupCH(self, inventory):
        """ Call it from CH spiders """
        self.inventory = inventory

    def _variants(self):
        variants = []

        if self.inventory.get('relatedProducts'):
            i = 0
            for property in self.inventory['relatedProducts'].keys():
                j = 0
                for product in self.inventory['relatedProducts'][property]:
                    if i == 0:
                        variant = {
                            'in_stock': product['isavlbl'] == 'yes',
                            'properties': {
                                property: product['value']
                            },
                        }

                        if product.get('key'):
                            variant['sku'] = product['key'][3:]

                        variants.append(variant)
                    else:
                        if j == 0:
                            for variant in variants:
                                variant['properties'][property] = product['value']
                        else:
                            for variant in copy.deepcopy(variants):
                                variant2 = copy.deepcopy(variant)
                                variant2['properties'][property] = product['value']

                                variant2['in_stock'] = not (product['isavlbl'] == 'no')
                                variants.append(variant2)
                    j += 1
                i += 1

        if variants:
            return variants

