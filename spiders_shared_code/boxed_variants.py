from lxml import html
import re
import base64
import json

class BoxedVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _get_product_json(self):
        product_json = None
        encoded_data = re.search(r'BoxedAppState\ =\ \'(.*?)\';', html.tostring(self.tree_html))
        if encoded_data:
            product_json = json.loads(base64.b64decode(encoded_data.group(1)))
        return product_json

    def _variants(self):
        variant_list = []
        product_json = self._get_product_json()
        if product_json:
            if product_json['productPayload']['product']['variants']:
                for variant_json in product_json['productPayload']['product']['variants']:
                    if variant_json['variant']['dro']['inventoryThreshold'] == 0: continue
                    variant = {}
                    variant['price'] = variant_json['variant']['price']
                    for option in variant_json['variant']['variantOptions']:
                        variant[option['optionType'].lower()] = option['optionValue']
                    variant_list.append(variant)
        return variant_list if len(variant_list) > 1 else None