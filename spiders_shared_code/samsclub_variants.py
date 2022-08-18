import re
import json
import mmh3
import requests
import traceback
from lxml import html

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:24.0) Gecko/20140319 Firefox/24.0 Iceweasel/24.4.0'}

class SamsclubVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = html.fromstring(response.body)
        self.product_json = None

    def setupCH(self, tree_html, product_json):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.product_json = product_json

    def _clean_text(self, text):
        text = text.replace("<br />"," ").replace("\n"," ").replace("\t"," ").replace("\r"," ")
       	text = re.sub("&nbsp;", " ", text).strip()
        return  re.sub(r'\s+', ' ', text)

    def _get_alternate_variants_json(self):
        if self.product_json:
            return self.product_json['product'].get('variants')

        product_json = re.search('window.__WML_REDUX_INITIAL_STATE__\s*=\s*({.*?});', html.tostring(self.tree_html))

        if product_json:
            product_json = json.loads(product_json.group(1))
            return product_json['product'].get('variants')

    def _variants(self):
        variants = []

        variants_json = self.tree_html.xpath("//div[@id='skuVariantDetailsJSON']/text()")

        if variants_json:
            variants_json = json.loads(variants_json[0].strip())

            for variant_json in sorted(variants_json.values()):
                variant = {
                    'in_stock': variant_json['status'] == 'Available',
                    'properties': {},
                    'upc': variant_json.get('upcId'),
                }

                for key, value in variant_json.iteritems():
                    if key not in ['status', 'upcId', 'isColorVariance']:
                        variant['properties'][key] = value

                variants.append(variant)

            return variants

        variants_json = self._get_alternate_variants_json()

        if variants_json:
            for prop in variants_json:
                for item in prop['items']:
                    v = {
                        'in_stock': item['status'] == 'in stock',
                        'selected': item['selected'],
                        'properties': {
                            prop['id'] : item['name']
                        }
                    }

                    variants.append(v)

                return variants

    def _swatches(self):
        swatches = []

        swatch_images = self.tree_html.xpath('//li[@class="swatchDefault"]/span/img')

        if not swatch_images or self.product_json:
            variants_json = self._get_alternate_variants_json()

            if variants_json:
                for prop in variants_json:
                    if prop['id'] == 'color':
                        swatch_images = prop['items']

        for img in swatch_images:
            hero_image = 'https:' + img.get('src') if img.get('src') else img['swatchImageUrl']

            try:
                response = requests.get(hero_image, headers = HEADERS, timeout=10)
                if mmh3.hash(response.content) == -1902766634:
                    hero_image = []
                else:
                    hero_image = [hero_image]
            except:
                print traceback.format_exc()
                hero_image = [hero_image]
 
            swatch = {
                'color': img.get('alt') or img['name'],
                'hero': len(hero_image),
                'hero_image': hero_image
            }
            swatches.append(swatch)

        if swatches:
            return swatches
