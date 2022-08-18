import re
import json
import traceback
from lxml import html
from urlparse import urljoin


class BestBuyVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = html.fromstring(response.body)
        self.product_page_url = response.url

    def setupCH(self, tree_html, product_page_url):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.product_page_url = product_page_url

    def _variants(self):
        try:
            variants = []

            variants_data = json.loads(re.search(".product-variations',\s*({.*}),.*?}", html.tostring(self.tree_html)).group(1))

            category_map = {}
            state_map = {}

            for category in variants_data['categories']:
                category_map[category['id']] = category['name']

                for variation in category['variations']:
                    state_map[variation['name']] = variation['state']

            for variant_data in variants_data['variationSkus']:
                for sku in variant_data['skus']:
                    sku_found = False

                    for variant in variants:
                        if variant.get('sku_id') == sku:
                            variant['properties'][category_map[variant_data['categoryId']]] = variant_data['name']
                            variant['selected'] = variant['selected'] and state_map[variant_data['name']] == 'selected'
                            sku_found = True
                            break

                    if not sku_found:
                        variant = {
                            'sku_id': sku,
                            'properties': {
                                category_map[variant_data['categoryId']]: variant_data['name']
                            },
                            'selected': state_map[variant_data['name']] == 'selected',
                            'unavailable': state_map[variant_data['name']] == 'disabled'
                        }

                        variants.append(variant)

            if variants:
                return variants
        except:
            print traceback.format_exc()
