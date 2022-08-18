import json
import re
import traceback

import lxml.html
import requests
from lxml import html

class JcpenneyVariants(object):

    def __init__(self):
        self.product_json = {}
        self.product_json_fetched = False

    def setupCH(self, tree_html, product_json={}, availability_dict={}, prices_json={}):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.variant_list = []
        self.swatch_list = []
        self.product_json = product_json
        self.availability_dict = availability_dict
        self.prices_json = prices_json
        self.variants_checked = False

    def swatches(self):
        self.variants()
        return self.swatch_list

    def all_variants(self):
        self.variants()
        return self.all_variant_list

    def variants(self):

        if self.variants_checked:
            return self.variant_list

        self.variants_checked = True
        variants = []
        properties_dict = self._properties_dict(self.product_json)

        for lot in self.product_json.get('lots', []):
            items = lot.get('items', [])
            for item in items:
                sku_id = item.get('id')

                variant = {}

                variant['in_stock'] = self.availability_dict.get(sku_id)
                variant['properties'] = {'sku': sku_id}
                variant['price'] = self.prices_json.get(sku_id)
                variant['selected'] = False

                for option_id in item.get('options', []):
                    option_data = properties_dict.get(option_id)
                    option_name = option_data.get('name')
                    option_value = option_data.get('value')
                    variant['properties'][option_name] = option_value

                variants.append(variant)

        # Reformat variants properties for consistency, see BZ #9913 or CON-27755
        variants = self.transform_jcpenney_variants(variants)

        # save info for all variants, even if there is just 1
        self.all_variant_list = variants

        if len(variants) > 1:
            self.variant_list = variants
            return self.variant_list

    @staticmethod
    def transform_jcpenney_variants(variants):
        for i, variant in enumerate(variants):
            properties = variant.get('properties', None)
            if 'lot' in variant and 'lot' not in properties:
                properties['lot'] = variant.pop('lot')
            if properties:
                # BZ case 2
                if 'waist' in properties:
                    waist_value = properties.pop('waist')
                    properties['size'] = waist_value
                # BZ case 3
                if 'size' in properties and 'size range' in properties:
                    size_range_value = properties.pop('size range')
                    size_value = properties.pop('size')
                    properties['size'] = "{}/{}".format(size_range_value, size_value)
                else:
                    # BZ case 1
                    if 'inseam' in properties and 'length' not in properties:
                        inseam_value = properties.pop('inseam')
                        properties['length'] = inseam_value

            variants[i]['properties'] = properties

        return variants

    def _properties_dict(self, product_json):
        properties_dict = {}

        for p in product_json.get('dimensions', []):
            options = p.get('options', [])
            name = p.get('name')
            for option in options:
                option_id = option.get('id')
                value = option.get('value')
                properties_dict[option_id] = {'name': name, 'value': value}

                if option.get('productImage'):
                    self.swatch_list.append({
                        'color': value,
                        'hero': 1,
                        'hero_image': [option.get('productImage').get('url', '').split('?')[0]],
                        'swatch_name': 'color',
                        'thumb': 1,
                        'thumb_image': [option.get('image', {}).get('url')]
                    })

        return properties_dict
