import re
import json
import traceback
from lxml import html


class WayfairVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    @staticmethod
    def _get_in_stock(option_id, data):
        try:
            for option in data:
                if int(option_id) in option.get('option_ids') or []:
                    return option.get('available_quantity') != 0
        except:
            print traceback.format_exc()

    def _variants(self, instock_options):
        variants = []
        js = re.findall(
            'wf.extend\(({"wf":{"apnData.*})\)',
            html.tostring(self.tree_html)
        )

        for elem in js:
            try:
                app_data = json.loads(elem)['wf']['reactData']
                for key in app_data.keys():
                    if app_data[key]['bootstrap_data'].get('options'):
                        variants_json = app_data[key]['bootstrap_data']
                break
            except:
                print traceback.format_exc()
        else:
            variants_json = {}

        base_price = variants_json.get('price', {}).get('salePrice')
        product_variants = variants_json.get('options', {}).get('standardOptions')
        selected_options = variants_json.get('options', {}).get('selectedOptions') or []

        if product_variants:
            product_variants = product_variants[0]

            for product_variant in product_variants.get('options') or []:
                if product_variant:
                    variant = {}
                    properties = {}

                    option_id = product_variant.get('option_id')

                    key = product_variant.get('category', '').lower()
                    if key:
                        properties[key] = product_variant.get('name')

                    variant['properties'] = properties
                    variant['in_stock'] = self._get_in_stock(option_id, instock_options)
                    variant['selected'] = option_id in selected_options

                    delta_price = float(product_variant.get('cost', 0))
                    if base_price:
                        variant['price'] = round(base_price + delta_price, 2)

                    variants.append(variant)

        if variants:
            return variants
