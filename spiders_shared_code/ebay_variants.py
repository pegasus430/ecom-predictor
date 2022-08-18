import re
import json
from lxml import html

class EbayVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.raw_text = response.body

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.raw_text = html.tostring(tree_html)

    def _get_product_json(self):
        variant_names = re.findall(r'"menuItemMap":(.*?)\}\},"', self.raw_text)
        try:
            variant_names = json.loads(variant_names[0] + '}}')
        except:
            variant_names = {}
        variant_items = re.findall(r'"itemVariationsMap":(.*?)\}\},"', self.raw_text)
        try:
            variant_items = json.loads(variant_items[0] + '}}')
        except:
            variant_items = {}

        unavailable_items = re.findall(r'"unavailableVariationIds":\[(.*?)\]', self.raw_text)
        if unavailable_items:
            unavailable_items = unavailable_items[0].split(',')
        map_images = re.findall(r'"menuItemPictureIndexMap":(.*?)},"', self.raw_text)
        try:
            map_images = json.loads(map_images[0] + '}')
        except:
            map_images = {}

        images = re.findall(r'"fsImgList":(.*?)\}\],', self.raw_text)
        try:
            images = json.loads(images[0] +'}]')
        except:
            images = []
        return variant_names, variant_items, unavailable_items, map_images, images

    def _variants(self):
        variant_list = []
        variant_names, variant_items, unavailable_items, map_images, images = self._get_product_json()

        for key, item in variant_items.iteritems():
            properties = item.get('traitValuesMap', {})
            image_url = None
            for idx, prop in properties.iteritems():
                if map_images.get(str(prop), []):
                    image = images[map_images.get(str(prop), [])[0]]
                    image_url = image.get('maxImageUrl') if image else None
                try:
                    properties[idx] = variant_names[str(prop)].get('valueName')
                except:
                    properties[idx] = None
            variant = {
                'unavailable': key in unavailable_items,
                'in_stock': item.get('inStock', False),
                'image_url': image_url,
                'price': item.get('priceAmountValue', {}).get('value'),
                'sku': key,
                'properties': properties
            }
            variant_list.append(variant)
        return variant_list