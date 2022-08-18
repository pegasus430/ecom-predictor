import json

import lxml.html
import re

def is_empty(x, y=None):
    if x:
        return x[0]
    else:
        return y


def normalize_product_json_string(product_json_string):
    # 1st issue pattern ex ----> "\tRustic Woodland":
    product_json_string = re.sub('[\t\n]', '', product_json_string)

    return product_json_string


class MacysVariants(object):
    IMAGE_BASE_URL = "http://slimages.macysassets.com/is/image/MCY/products/"

    def setupSC(self, response, is_bundle=False):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = lxml.html.fromstring(response.body)
        self.is_bundle = is_bundle

    def setupCH(self, tree_html, is_bundle=False):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.is_bundle = is_bundle

    def _extract_product_info_json(self):
        try:
            return json.loads(normalize_product_json_string(
                self.tree_html.xpath('//script[@data-bootstrap="feature/product"]/text()')[0]))
        except:
            print "Parsing error of product info json"
        return None

    def _variants(self):
        # New layout parsing draft. Should be detailed later.
        variants = []
        data = self._extract_product_info_json()
        if not data:
            return variants

        variants_data = data.get('product', {}).get('traits', {})
        sizes = variants_data.get('sizes', {}).get('sizeMap', [])
        colors = variants_data.get('colors', {}).get('colorMap', [])
        selected_id = variants_data.get('colors', {}).get('selectedColor')

        image_prefix = 'http://slimages.macysassets.com/is/image/MCY/products/{}'
        variants_root = colors
        for key, variant_data in variants_root.iteritems():
            variant = {
                'in_stock': True,
                'selected': key == selected_id,
                'product_name': variant_data.get('name', 'no name'),
                'img_urls': [image_prefix.format(image.get('filePath'))
                             for image in variant_data.get('imagery', {}).get('images', [])],
                'price': is_empty(is_empty(variant_data.get('pricing', {}).get('price', {})
                                           .get('tieredPrice', []), {}).get('values'), {}).get('value'),
                'properties': {
                    'size': ', '.join(sizes.get(unicode(size_id), {})
                                      .get('displayName') for size_id in variant_data.get('sizes', []))
                },
            }
            variants.append(variant)

        return variants
