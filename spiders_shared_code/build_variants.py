import re


class BuildVariants(object):

    def setupSC(self, product_json):
        """ Call it from SC spiders """
        self.product_json = product_json


    def setupCH(self, product_json):
        """ Call it from CH spiders """
        self.product_json = product_json

    def _variants(self):
        variants = []
        for variant in self.product_json.get('finishes', []):
            variants.append({
                'image_url': variant.get('images', {}).get('defaultImg'),
                'in_stock': not variant.get('isOutOfStock', True),
                'price': float(variant.get('consumerPrice')),
                'selected': variant.get('selectedFinish', False),
                'upc': variant.get('upc'),
                'properties': {
                    'finish': variant.get('finish')
                }
            })
        return variants if variants and len(variants) > 1 else None
