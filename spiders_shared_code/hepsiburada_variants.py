import re

class HepsiburadaVariants(object):

    def setupSC(self, variants, sku):
        """ Call it from SC spiders """
        self.variants = variants
        self.sku = sku

    def setupCH(self, variants, sku):
        self.variants = variants
        self.sku = sku

    def _variants(self):
        variant_list = []
        for datum in self.variants:
            variant = {}
            variant['in_stock'] = datum.get('isInStock', False)
            variant['price'] = datum.get('price', {}).get('value')
            variant['sku_id'] = datum.get('sku')
            variant['image_url'] = datum.get('thumbnail')
            variant['properties'] = {}
            variant['selected'] = variant['sku_id'] == self.sku
            for property in datum.get('properties', []):
                name = property.get('displayName')
                value = property.get('valueObject', {}).get('actualValue')
                if not name and not value:
                    continue
                variant['properties'][name] = value
            variant_list.append(variant)
        return variant_list
