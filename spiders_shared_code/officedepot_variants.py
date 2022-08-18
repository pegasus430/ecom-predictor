import re
import lxml.html

try:
    from scrapy import log
    scrapy_imported = True
except:
    scrapy_imported = False


class OfficedepotVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self, variants_json=None):
        variant_list = []

        if not variants_json:
            return

        if variants_json.get('success'):
            for sku in variants_json.get('skus', []):
                price = re.findall(
                    '\$([\d\.]+)', sku.get('attributesDescription', ''))
                name = sku.get('description', '')

                variant_item = {
                    'image_url': sku.get('thumbnailImageUrl').split('?')[0],
                    'properties': {
                        'title': name if name else None
                    },
                    'in_stock': True,
                    'sku_id': sku.get('sku'),
                    'price': float(price[0]) if price else None
                }

                variant_list.append(variant_item)

        if variant_list:
            return variant_list
