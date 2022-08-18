from lxml import html


class LowesCaVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self):
        variants = self.tree_html.xpath('//div[@itemtype="http://schema.org/Offer"]')
        variant_list = []
        for variant in variants:
            variant_value = {}
            sku = variant.xpath('.//meta[@itemprop="sku"]/@content')
            variant_value['properties'] = {}
            if sku:
                variant_value['sku_id'] = sku[0]
                color_name = self.tree_html.xpath('//option[@name="{sku}" and not(@value="0")]/text()'.format(sku=sku[0]))
                variant_value['properties']['color'] = color_name[0] if color_name else None
            price = variant.xpath('.//meta[@itemprop="price"]/@content')
            variant_value['price'] = float(price[0].replace(',', '')) if price else None
            instock = variant.xpath('.//meta[@itemprop="availability"]/@content')
            if instock:
                variant_value['in_stock'] = instock[0] == 'http://schema.org/InStock'
            else:
                variant_value['in_stock'] = False
            variant_list.append(variant_value)
        return variant_list if variant_list else None
