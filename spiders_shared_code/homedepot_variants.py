import copy
from lxml import html


class HomeDepotVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def swatches(self):
        swatches = []

        for img in self.tree_html.xpath('//div[contains(@class, "sku_variant")]/ul/li/a/img'):
            swatch = {
                'color': img.get('title'),
                'hero': 1,
                'hero_image': [img.get('src')]
            }
            swatches.append(swatch)

        if swatches:
            return swatches

    @staticmethod
    def _get_unavaliable_variants(html, data):
        oos_variants = []
        oos_options = html.xpath(
            '//a[@class="disabled" and @data-itemid]/text()'
        )
        for oos_option in oos_options:
            properties = {}
            for property in data.get('definingAttributes'):
                properties[property['attributeName']] = property['attributeValue']
            prop_name = html.xpath(
                '//div[@class="attribute_label"]/text()'
            )
            if prop_name:
                properties[prop_name[0]] = oos_option
            oos_variants.append({
                'in_stock': False,
                'selected': False,
                'properties': properties
            })
        return oos_variants

    def variants(self, variants_data):
        variants = []
        for variant_data in variants_data:
            for variant in variant_data.get('options'):
                data = variant.get('json', {}).get('primaryItemData', {})
                tmp = {
                    'image_url': data.get('media', {}).get('mediaList', [{}])[0].get('location'),
                    'in_stock': True,
                    'price': data.get('itemExtension', {}).get('pricing', {}).get('specialPrice'),
                    'selected': variant.get('selected'),
                    'upc': data.get('info', {}).get('upc'),
                    'properties': {}
                }
                for property in data.get('definingAttributes'):
                    tmp['properties'][property['attributeName']] = property['attributeValue']
                variants.append(tmp)
            variants.extend(self._get_unavaliable_variants(variant_data.get('html'), data))

        if variants:
            return variants
