import re
import json
import base64
import traceback
from lxml import html

class CostcoVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    @staticmethod
    def _get_variants_json(tree_html):
        variants_data = re.search(r'var products\s=\s\[(.*?)\];', html.tostring(tree_html), re.DOTALL)
        if variants_data:
            try:
                variants_data = json.loads(variants_data.group(1))
            except ValueError:
                print('Can\'t load variants json data: {}'.format(traceback.format_exec()))
                variants_data = None
        return variants_data

    @staticmethod
    def _get_options_dict(tree_html):
        options = {}
        option_elements = tree_html.xpath('//option[@class="opt"]')
        for element in option_elements:
            key = element.xpath('./@value')
            value = element.xpath('./text()')
            option_name = element.xpath('./@data-attr-name')
            if key and value and option_name:
                options.update({
                    key[0]: {
                        'data': value[0],
                        'option_name': option_name[0]
                    }
                })
        return options

    def _variants(self):
        variants = []
        variants_data = self._get_variants_json(self.tree_html)
        options = self._get_options_dict(self.tree_html)
        for variant in variants_data:
            data = {
                'image_url': variant.get('img_url'),
                'in_stock': variant.get('inventory') == 'IN_STOCK',
                'price': base64.b64decode(variant.get('price')),
                'selected': False,
            }
            for prop in variant.get('options'):
                option_data = options.get(prop)
                if option_data:
                    data.setdefault('properties', {})[option_data['option_name']] = option_data['data']
            variants.append(data)
        return variants if variants and len(variants) > 1 else None
