
class SephoraVariants(object):

    def setupSC(self, product_json):
        """ Call it from SC spiders """
        self.product_json = product_json

    def setupCH(self, product_json):
        """ Call it from CH spiders """
        self.product_json = product_json

    def _variants(self):
        property = self.product_json.get('variationType')
        variant_list = []
        for sku in self.product_json.get('regularChildSkus', []):
            variant = {
                "image_url": None,
                "in_stock": not sku.get('isOutOfStock', False),
                "price": None,
                "properties": {
                    property: sku.get('variationValue')
                },
                "selected": sku.get('skuId') == self.product_json.get('currentSku').get('skuId'),
                "sku_id": sku.get('skuId'),
            }
            image_url = sku.get('skuImages', {}).get('image1500')
            variant['image_url'] = 'https://www.sephora.com' + image_url if image_url else None
            variant['price'] = float(sku.get('listPrice')[1:].replace(',', '')) if sku.get('listPrice') else None
            variant_list.append(variant)
        return variant_list if variant_list else None
