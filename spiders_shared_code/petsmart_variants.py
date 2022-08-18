import re
import json
import urllib
from lxml import html

class PetsmartVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self):
        def fix_variant(variant):
            v = {
                'image_url': variant.get('image'),
                'in_stock': not(variant.get('outOfStock')),
                'price': variant.get('price'),
                'properties': {}
            }

            if variant.get('customFlavor'):
                v['properties']['flavor'] = variant['customFlavor']

            for prop in ['color', 'size']:
                if variant.get(prop):
                    v['properties'][prop] = variant[prop]

            return v

        variants_json = re.search('"trackProductView", "(.*?)"', html.tostring(self.tree_html)).group(1)
        variants_json = json.loads(urllib.unquote(variants_json))
        variants = variants_json.get('variants') or []

        if len(variants) > 1:
            return [fix_variant(v) for v in variants]
