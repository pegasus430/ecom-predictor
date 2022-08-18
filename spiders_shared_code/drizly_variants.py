import re
import json
from lxml import html

class DrizlyVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _get_variants_json(self):
        product_json_data = self.tree_html.xpath('//div[@data-integration-name="redux-store"]/@data-payload')
        if product_json_data is not None:
            return json.loads(product_json_data[0])

    def _variants(self):
        variants_json = self._get_variants_json()
        variants = []
        selected_key = variants_json.get('props', {}).get('selectedVariantId')
        for key, variant_data in variants_json.get('props', {}).get('availabilityMap', {}).get('map', {}).iteritems():
            variant_data = variant_data[0]
            variants.append(
                {
                    "in_stock": variant_data.get('available'),
                    "price": variant_data.get('price_raw'),
                    "selected": key == selected_key,
                    "properties": {
                        "type quantity": variant_data.get('short_description')
                    }
                }
            )
        return variants if variants and len(variants) > 1 else None
