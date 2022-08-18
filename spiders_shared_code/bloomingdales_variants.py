class BloomingDalesVariants(object):

    def setupSC(self, product_json):
        self.upcs = product_json.get('upcs', [])
        self.images = product_json.get('colorwayPrimaryImages', {})

    def setupCH(self, product_json):
        self.upcs = product_json.get('upcs', [])
        self.images = product_json.get('colorwayPrimaryImages', {})

    def _variants(self):
        variant_list = []
        for upc in self.upcs:
            properties = {}
            color = upc.get('colorway', {}).get('colorName')
            if color:
                properties['color'] = color

            size = upc.get('attributes', {}).get('SIZE', [])
            if size:
                properties['size'] = size[0]
            image_url = self.images.get(color)
            image_url = 'https://images.bloomingdales.com/is/image/BLM/products/' + image_url if image_url else None
            variant = {
                'upc': upc.get('upc'),
                'price': upc.get('price').get('retailPrice'),
                'unavailable': not upc.get('available'),
                'properties': properties,
                'image_url': image_url
            }
            variant_list.append(variant)

        return variant_list if variant_list else None
