import re
from lxml import html
from urlparse import urljoin


class AdoramaVariants(object):

    def setupSC(self, response, variants_json):
        """ Call it from SC spiders """
        self.tree_html = html.fromstring(response.body)

    def setupCH(self, tree_html, variants_json):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.data = variants_json

    def _variants(self):
        variants = []
        prop_names = [
            x.replace(':', '').strip() for x in self.tree_html.xpath(
                '//div[contains(@class, "product-options")]//nav/strong/text()'
            )
        ]
        props_base = {}
        prop_sections = self.tree_html.xpath(
            '//div[contains(@class, "product-options")]//nav/span[contains(@class, "selected")]/@title'
        )
        if prop_sections:
            for k, x in enumerate(prop_sections):
                props_base[prop_names[k]] = x.strip()
        data = self.data.get('data')
        current_sku = self.tree_html.xpath('//section[@data-sku]/@data-sku')
        for key in data.keys():
            props = props_base.copy()
            image_url = data.get(key, {}).get('images', {})
            if image_url:
                image_url = urljoin(
                    'https://www.adorama.com/images/Large/',
                    image_url[0].get('name')
                )
            curr_prop_key = self.tree_html.xpath(
                '//a[contains(@data-track-data, "%s")]/parent::nav/strong/text()' % data.get(key, {}).get('id')
            )
            curr_prop_val = self.tree_html.xpath(
                '//a[contains(@data-track-data, "%s")]/img/@alt' % data.get(key, {}).get('id')
            )
            if not curr_prop_val:
                curr_prop_val = self.tree_html.xpath(
                    '//a[contains(@data-track-data, "%s")]/text()' % data.get(key, {}).get('id')
                )
            if curr_prop_key and curr_prop_val:
                props[curr_prop_key[0].replace(':', '').strip()] = curr_prop_val[0].strip()
            variants.append(
                {
                    "image_url": image_url if image_url else None,
                    "in_stock": data.get(key, {}).get('stock') == 'In',
                    "price": data.get(key, {}).get('prices', {}).get('price'),
                    "properties": props,
                    "selected": data.get(key, {}).get('id') == current_sku,
                    "sku_id": data.get(key, {}).get('id'),
                }
            )
        return variants if variants else None
