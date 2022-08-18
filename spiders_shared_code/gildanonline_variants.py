from urlparse import urljoin

class GildanOnlineVariants(object):

    def setupSC(self, skus):
        """ Call it from SC spiders """
        self.skus = skus

    def _variants(self):
        variants = []
        for item in self.skus:
            variant = {}
            variant['sku_id'] = item.get('id')
            price = item.get('pricePair', {}).get('salePrice')
            if not price:
                price = item.get('pricePair', {}).get('listPrice')
            variant['price'] = price
            variant['image_url'] = urljoin('https://www.gildan.com/assets/img/catalog/product/small/',
                                           item.get('skuImage')) if item.get('skuImage') else None
            variant['inStock'] = item.get('onSale')
            variant['properties'] = {}
            for option in item.get('relatedOptions', []):
                if option.get('name') and option.get('value'):
                    variant['properties'][option.get('name')] = option.get('value')
            variants.append(variant)

        return variants
