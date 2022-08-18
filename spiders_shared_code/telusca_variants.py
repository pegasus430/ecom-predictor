# ~~coding=utf-8~~
import json
import lxml.html
import traceback

from .utils import deep_search


class TelusCAVariants(object):

    def setupSC(self, response, product_url=None):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = lxml.html.fromstring(response.body)
        self.product_url = product_url

    def setupCH(self, tree_html, product_url=None):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.product_url = product_url

    def _variants(self):
        variants = []
        product_info = self.get_product_data()
        product_data = deep_search('accessories', product_info)

        if not product_data:
            product_data = deep_search('phones', product_info)

        if not product_data:
            return None
        else:
            product_data = product_data[0]

        for data in product_data:
            variant = {
                'in_stock': data.get('consumerInStock') or data.get('consumerActive'),
                'price': data.get('salePrice') or data.get('basePrice'),
            }
            if data.get('sku'):
                variant['sku'] = data.get('sku')
            if data.get('upc'):
                variant['upc'] = data.get('upc')
            properties = {}
            if data.get('storage', {}).get('ref'):
                properties['size'] = data.get('storage', {}).get('ref')
            if data.get('colour', {}).get('name'):
                properties['color'] = data.get('colour', {}).get('name')
            variant['properties'] = properties
            variants.append(variant)

        if variants and len(variants) > 1:
            return variants

    def get_product_data(self):
        try:
            product_json = self._find_between(lxml.html.tostring(self.tree_html), '__INITIAL_STATE__ =', 'window.__LOCALE__').strip()[:-1]
            product_data = json.loads(product_json).get('contentful')
        except Exception as e:
            print traceback.format_exc(e)
            product_data = None

        return product_data

    def _find_between(self, s, first, last, offset=0):
        try:
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""
