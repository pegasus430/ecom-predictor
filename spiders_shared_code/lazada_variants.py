import re
import lxml.html
import traceback
import json
import requests
from urlparse import urljoin


class LazadaVariants(object):

    def setupSC(self, response, product_page_url):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)
        self.product_page_url = product_page_url
        self._extract_inline_json()

    def setupCH(self, tree_html, product_page_url):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.product_page_url = product_page_url
        self._extract_inline_json()

    def _extract_inline_json(self):
        data = re.search(r'app.run\((.*?})\);', lxml.html.tostring(self.tree_html), re.DOTALL)
        try:
            self.product_json = json.loads(data.group(1))['data']['root']['fields']
        except:
            print traceback.format_exc()

    def _variants(self):
        if not self.product_json:
            return None

        variants = []
        skus_list = self.product_json.get('productOption', {}).get('skuBase', {}).get('skus', [])

        properties = []
        properties_list = self.product_json.get('productOption', {}).get('skuBase', {}).get('properties', [])
        for prop in properties_list:
            values = prop.get('values')
            if not values:
                continue

            for value in values:
                for sku in skus_list:
                    if value.get('vid') in sku.get('propPath'):
                        value['skuId'] = sku.get('skuId')
                        value['sku'] = sku.get('innerSkuId')
                        value['url'] = sku.get('pagePath')

            properties.append({
                'name': prop.get('name'),
                'values': values
            })

        sku_infos = self.product_json.get('skuInfos', {})
        selected_sku_id = None

        for sku_id, sku_info in sku_infos.items():
            if sku_id == '0':
                selected_sku_id = sku_info.get('skuId')
                continue

            image = 'https:' + sku_info['image'] if sku_info.get('image') else None
            props = {}
            sku = None
            url = None
            for prop in properties:
                prop_name = prop.get('name')
                for value in prop.get('values', []):
                    if sku_id == value.get('skuId'):
                        sku = value.get('sku')
                        props[prop_name] = value.get('name')
                        url = urljoin(self.product_page_url, value.get('url'))
            price = sku_info.get('price', {}).get('salePrice', {}).get('value')
            if not price:
                price = sku_info.get('price', {}).get('originalPrice', {}).get('value')
            if not price and url:
                price = float(re.search('"price":(.*?),', requests.get(url).content).group(1))

            variants.append({
                'sku': sku,
                'url': url,
                'properties': props,
                'price': price,
                'image_url': image,
                'in_stock': True if sku_info.get('stock') else False,
                'selected': selected_sku_id == sku_info.get('skuId')
            })

        return variants if variants else None
