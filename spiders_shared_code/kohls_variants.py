import re
import json
import traceback
from lxml import html
try:
    from scrapy import log

    scrapy_imported = True
except:
    scrapy_imported = False

class KohlsVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _extract_product_info_json(self):
        product_json_data = re.search('var productV2JsonData = ({.*?});', html.tostring(self.tree_html))
        try:
            return json.loads(product_json_data.group(1))
        except:
            log(traceback.format_exc())
        return {}

    def _variants(self):
        product_info_json = self._extract_product_info_json()

        variants = []
        sale_price = product_info_json.get('price', {}).get('salePrice')
        if sale_price:
            price = sale_price.get('minPrice')
        else:
            price = product_info_json.get('price', {}).get('regularPrice', {}).get('minPrice')
        available_variants = product_info_json.get('SKUS', [])
        colors = product_info_json.get('variants', {}).get('colorList')
        sizes = product_info_json.get('variants', {}).get('sizeList')
        product_url = product_info_json.get('productURL')

        if colors and sizes:
            for color in colors:
                for size in sizes:
                    variant = {
                        'price': price,
                        'properties': {
                            'color': color,
                            'size': size
                        },
                        'url': product_url
                    }
                    additional_info = [prod for prod in available_variants if
                                       variant['properties']['color'] == prod.get('color')
                                       and variant['properties']['size'] == prod.get('size')]
                    variant['in_stock'] = bool(additional_info)
                    variant['upc'] = additional_info[0].get('UPC', {}).get('ID') if additional_info else None
                    variants.append(variant)
        elif colors:
            for color in colors:
                variant = {
                    'price': price,
                    'properties': {
                        'color': color
                    },
                    'url': product_url
                }
                additional_info = [prod for prod in available_variants if
                                   variant['properties']['color'] == prod.get('color')]
                variant['in_stock'] = bool(additional_info)
                variant['upc'] = additional_info[0].get('UPC', {}).get('ID') if additional_info else None
                variants.append(variant)
        elif sizes:
            for size in sizes:
                variant = {
                    'price': price,
                    'properties': {
                        'size': size
                    },
                    'url': product_url
                }
                additional_info = [prod for prod in available_variants if
                                   variant['properties']['size'] == prod.get('size')]
                variant['in_stock'] = bool(additional_info)
                variant['upc'] = additional_info[0].get('UPC', {}).get('ID') if additional_info else None
                variants.append(variant)

        return variants if variants else None
