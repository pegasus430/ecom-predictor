import re
import json
from lxml import html
import traceback


class ShoebuyVariants(object):

    IMG_BASE_URL = 'https://cdn-us-ec.yottaa.net/550c587c2106b06b5100362d/www.shoes.com/v~13.7f/pi/'

    def setupSC(self, response, product_json):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = html.fromstring(response.body)
        self.product_json = product_json

    def setupCH(self, tree_html, product_json):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.product_json = product_json

    def _get_variant_info(self):
        try:
            c = html.tostring(self.tree_html)
            variant_info = re.search('productCollection.addProductObject\(1, ({.*?})\);', c)
            return json.loads(variant_info.group(1))
        except:
            self.log("Error while get variant info: {}".format(traceback.format_exc()))
            return None

    def swatches(self):
        swatches = []

        variant_info = self._get_variant_info()

        if variant_info:
            for color in variant_info.get('colors', []):
                s = {
                    'color': color['name'],
                    'hero': 1,
                    'hero_image': [self.IMG_BASE_URL + color['lgURL']],
                }

                swatches.append(s)

            return swatches

    def _variants(self):
        variants = []

        variant_info = self._get_variant_info()

        if variant_info:
            for i, color in enumerate(variant_info.get('colors', [])):
                for j, size in enumerate(variant_info.get('sizes', [])):
                    for k, width in enumerate(variant_info.get('widths', [])):
                        v = {
                            'in_stock': bool(variant_info['skus'][j][k][i]),
                            'price': float(color['price']) / 100,
                            'properties': {
                                'color': color['name'] if 'name' in color else None,
                            },
                            'selected': False
                        }

                        if size[0] != 'None':
                            v['properties']['size'] = size[0]

                        if width[0] != 'None':
                            v['properties']['width'] = width[0]

                        variants.append(v)

            return variants