import re
import json
import traceback
from lxml import html


class DockersVariants(object):

    def setupSC(self, response, ignore_color_variants, selected_sku):
        """ Call it from SC spiders """
        self.tree_html = html.fromstring(response.body)
        self.ignore_color_variants = ignore_color_variants
        self.selected_sku = selected_sku
        self.swatches = []

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.ignore_color_variants = False
        self.swatches = []

    def _extract_product_json(self):
        product_json = None
        try:
            product_json = json.loads(
                self._clean_text(self._find_between(html.tostring(self.tree_html), 'LSCO.dtos = ', 'LSCO.findFeatureValues'))
            )
        except:
            print traceback.format_exc()

        return product_json

    def _variants(self, variants_data):
        variants = []
        product_json = self._extract_product_json()
        variant_options = product_json.get('product', {}).get('variantOptions', [])

        for variant_option in variant_options:
            variant = {
                'sku_id': variant_option.get('code'),
                'price': variant_option.get('priceData', {}).get('value'),
                'in_stock': self._stock_status(variants_data, variant_option.get('code')),
            }
            if variant_option.get('colorName'):
                variant.setdefault('properties', {})['color'] = variant_option['colorName']
            if variant_option.get('displaySizeDescription'):
                variant.setdefault('properties', {})['size'] = variant_option['displaySizeDescription']
            variants.append(variant)
        return variants if variants else None

    @staticmethod
    def _stock_status(variants_data, sku):
        for x in variants_data.get('variantOptions', []):
            if x.get('code') == sku:
                return bool(x.get('stock', {}).get('stockLevel'))

    @staticmethod
    def _find_between(s, first, last, offset=0):
        try:
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t]", "", text).strip()
