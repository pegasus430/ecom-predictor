import re
import json

class JetVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.product_data = json.loads(response.body)['result']

    def setupCH(self, product_data):
        """ Call it from CH spiders """
        self.product_data = product_data

    def _parse_variant_data(self, variant_data, selected = False):
        props = {}

        variant_properties = variant_data.get('variantProperties') or variant_data.get('activeVariantProperties') or [{}]

        for prop in variant_properties:
            if prop.get('type') and prop.get('value'):
                props[prop['type']] = prop['value']

        image_url = variant_data.get('images')
        image_url = image_url[0].get('raw') if image_url else None

        # note: price is not present for non-main variants
        price = variant_data.get('productPrice', {}).get('referencePrice')

        return {
            'selected': selected,
            'properties': props,
            'price': price,
            'image_url': image_url,
            'sku': variant_data.get('retailSkuId') # include sku
        }

    def _variants(self):
        variants = []

        # parse the main variant
        variant = self._parse_variant_data(self.product_data, selected = True)
        # malformed variants don't have properties
        if variant.get('properties'):
            variants.append(variant)

        # parse the other variants
        for variant_data in self.product_data.get('productVariations', []):
            variant = self._parse_variant_data(variant_data)
            # malformed variants don't have properties
            if variant.get('properties'):
                variants.append(variant)

        if len(variants) > 1:
            return variants
