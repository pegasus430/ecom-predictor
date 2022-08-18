import urlparse
import itertools
import lxml.html

class TargetVariants(object):

    def setupCH(self, item_info, selected_upc):
        """ Call it from CH spiders """
        self.item_info = item_info
        self.selected_upc = selected_upc

    def _swatches(self):
        if self.item_info:
            swatches = []
            color_list = []

            for child in self.item_info['item'].get('child_items') or []:
                images = child['enrichment']['images'][0]

                if images.get('swatch'):
                    color = child['variation'].get('color')
                    if color:
                        hero_image = [images['base_url'] + images['swatch']]

                        swatch = {
                            'color': color,
                            'hero_image': hero_image,
                            'hero': len(hero_image)
                        }

                        if not color in color_list:
                            color_list.append(color)
                            swatches.append(swatch)

            return swatches if swatches else None

    def _parse_image_urls(self, data):
        images = []
        for image in data['enrichment']['images']:
            base_url = image['base_url']
            all_image_codes = [image['primary']] + image.get('alternate_urls', [])
            images += [urlparse.urljoin(base_url, '{}?scl=1'.format(image_id)) for image_id in all_image_codes]
        return images

    def _variants(self):
        if self.item_info:
            def _parse_variant(variant, selected, properties):
                image_urls = self._parse_image_urls(variant)

                variant = {
                    'selected': selected,
                    'upc': variant.get('upc'),
                    'properties': properties,
                    'price': variant['price']['offerPrice']['price'],
                    'url': variant['enrichment']['buy_url'],
                    'image_url': image_urls[0] if image_urls else None,
                    'in_stock': variant['available_to_promise_network']['availability'] != 'UNAVAILABLE' and \
                            variant['available_to_promise_network']['availability_status'] != 'OUT_OF_STOCK'
                }
                return variant

            def _parse_variant_properties(properties):
                properties = {k: v for x in properties for k, v in x.items()}
                for variant_properties in itertools.product(*properties.values()):
                    yield {
                        key: variant_property for key, variant_property in zip(properties.keys(), variant_properties)
                    }

            variants = []
            child_items = self.item_info['item'].get('child_items')
            if child_items:
                properties = self.item_info['item']['variation']['flexible_variation']
                for item, properties in zip(child_items, _parse_variant_properties(properties)):
                    selected = item.get('upc') == self.selected_upc
                    variant = _parse_variant(item, selected, properties)
                    variants.append(variant)
            return variants
