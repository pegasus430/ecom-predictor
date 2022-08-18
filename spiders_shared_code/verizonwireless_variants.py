import lxml.html
import json
import re


class VerizonWirelessVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _parse_variants_json(self, sku_list):
        if not sku_list:
            return None
        variants = []
        for sku in sku_list:
            if not sku.get('validSku') and sku.get('validSku') != None:
                continue

            vr = {}
            vr['skuID'] = sku.get('id')
            properties = {}
            color = sku.get('colorName')
            vr['in_stock'] = sku.get('inventoryStatus') == 1000
            if color:
                properties['color'] = color
            capacity = sku.get('capacity')
            if capacity:
                properties['capacity'] = capacity

            vr['properties'] = properties

            price = str(self._parse_sku_price_json(sku))

            if self._parse_sku_price_json(sku):
                price = float(price.replace('$', ''))
                if price != 0.00:
                    vr['price'] = price

            if vr['properties']:
                variants.append(vr)

        return variants if variants else None

    def _parse_sku_price_json(self, data):
        return data.get('priceBreakDown', {}).get(
            'fullRetailPriceListId', {}).get('RETAIL PRICE', None) or \
            data.get('price', {}).get('retailPrice')

    def _parse_variants_swatches(self, swatches):
        variants = []
        for swatch in swatches:
            vr = {}
            try:
                onclick = swatch.xpath('.//a/@onclick')[0]
                vr['skuID'] = re.search('sku\d+', onclick).group(0)
            except:
                pass

            vr['properties'] = {'color': swatch.xpath('.//a/@title')[0]}
            vr['selected'] = bool(swatch.xpath(
                './/a[contains(@class,"active")]'))

            variants.append(vr)
        return variants

    def _variants(self):
        content = lxml.html.tostring(self.tree_html)
        pdp_data = re.findall('pdpJSON = ({.*})', content)

        if pdp_data:
            pdp_json = json.loads(pdp_data[0])
            product_data = pdp_json.get('devices', {}) or \
                pdp_json.get('accessory', {})

            sku_list = product_data.get('skus', [])
            return self._parse_variants_json(sku_list)

        horizontal_list = self.tree_html.xpath('//*[@class="horizontalList colors"]/li')
        if horizontal_list:
            return self._parse_variants_swatches(horizontal_list)