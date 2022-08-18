import re
import copy
import json
import traceback

from lxml import html


class HayneedleVariants(object):
    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def product_json(self):
        try:
            return json.loads(
                re.search('window.__models__ = ({.*})',
                          html.tostring(self.tree_html))
                    .group(1)
            )
        except:
            print traceback.format_exc()

    def _variants(self):
        variants = []
        first_option = True

        for value in self.product_json().values():
            if value.get('optionData'):
                options = value.get('optionData').get('options')

                for op in options:
                    variants = []

                    name = op.get('name')
                    values = op.get('values')

                    for v in values:
                        variant = {
                            'image_url': v.get('img')[2:],
                            'in_stock': v.get('isAvailable'),
                            'selected': v.get('isSelected'),
                            'price_dict': v.get('price'),
                            'price': float(v.get('price').get('min')[1:]),
                            'properties': {name: v.get('name')}
                        }

                        if not first_option:
                            for original_variant in original_variants:
                                variant_copy = copy.deepcopy(original_variant)
                                variant_copy['image_url'] = variant_copy['image_url'] or variant['image_url']
                                variant_copy['in_stock'] = variant_copy['in_stock'] and variant['in_stock']
                                variant_copy['selected'] = variant_copy['selected'] and variant['selected']
                                variant_copy['properties'].update(variant['properties'])

                                for price in variant_copy['price_dict'].values():
                                    if price in variant['price_dict'].values():
                                        variant_copy['price'] = float(price[1:])

                                variants.append(variant_copy)

                        else:
                            variants.append(variant)

                    original_variants = copy.deepcopy(variants)
                    first_option = False

        if variants:
            for variant in variants:
                del variant['price_dict']
            return variants

