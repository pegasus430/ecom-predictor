import traceback
from lxml import html

try:
    from scrapy import log

    scrapy_imported = True
except:
    scrapy_imported = False


class AnthropologieVariants(object):
    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self, variants_json = None):
        try:
            variant_list = []

            elems = variants_json.get('product', {}).get('skuInfo', {}) \
                .get('primarySlice', {}).get('sliceItems', [])

            for elem in elems:
                color_name = elem.get('displayName')
                for variant in elem.get('includedSkus', []):
                    variant_item = {
                        'properties': {
                            'color': color_name,
                            'size': variant.get('size'),
                        },
                        'in_stock': bool(variant.get('stockLevel')),
                        'sku_id': variant.get('skuId'),
                        'price': variant.get('salePrice'),
                    }
                    variant_list.append(variant_item)

            if variant_list:
                return variant_list
        except:
            if scrapy_imported:
                    log.msg("Can't get sliceItems.{}".format(traceback.format_exc()))
