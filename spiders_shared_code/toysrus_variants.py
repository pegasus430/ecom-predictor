import lxml.html
import re
import json
import requests
import traceback

from lxml import html
from urlparse import urljoin


class ToysrusVariants(object):

    VARIANTS_URL = 'https://www.toysrus.com/jstemplate/ajaxPdpToGetPriceAndInventory.jsp?' \
                   'productIds={}&onlinePID={}'

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)
        self.product_page_url = response.url

    def setupCH(self, tree_html, product_page_url):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.product_page_url = product_page_url

    def _variants(self):
        variants = []
        variants_info = self._find_between(html.tostring(self.tree_html), "window.__INITIAL_STATE__ =", "window.__CONFIG__")
        if variants_info:
            try:
                skus_info = json.loads(variants_info).get('productDetails', {}).get('SKUsList', [])
                for sku in skus_info:
                    variants.append({
                        'image_url': sku.get('image'),
                        'sku_id': sku.get('id'),
                        'price': sku.get('salePrice'),
                        'in_stock': 1 if sku.get('isOutOfStock') is False else 0,
                        'properties': {
                            'sizes': sku.get('swatch').get('sizes'),
                            'color': sku.get('swatch').get('colorLabel'),
                        },
                        'available': sku.get('swatch').get('available'),
                        'upc': sku.get('upcNumber'),
                    })
                    if self.tree_html.xpath('//img[@src="%s"]/parent::div[contains(@class,"selected")]' % sku.get('swatch').get('image')):
                        variants[-1]['selected'] = True
                    else:
                        variants[-1]['selected'] = False
            except Exception as e:
                print 'Variants Data Error: {}'.format(traceback.format_exc(e))
        else:
            headers = {
                'accept': '*/*',
                'accept-encoding': 'gzip, deflate, br',
                'accept-language': 'en-US,en;q=0.8',
                'content-type': 'application/json',
                'origin': 'https//www.toysrus.com',
                'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36'
            }

            try:
                product_id = self.tree_html.xpath("//input[@id='onlinePID']/@value")[0]
                pid = self.tree_html.xpath("//input[@id='productId']/@value")[0]

                payload = {
                    'productIds': pid,
                    'onlinePID': product_id
                }

                variants_data = requests.post(
                    self.VARIANTS_URL.format(pid, product_id),
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=10
                )

                variants_info = json.loads(self._find_between(variants_data.text, 'pdpInventoryCheckJSON">', '<')).get(pid)

                if variants_info:
                    for i, vr in enumerate(variants_info.get('invenventoryAndPriceDetails', [])):
                        variants.append({
                            'image_url': vr.get('image'),
                            'sku_id': vr.get('skuId'),
                            'price': vr.get('salePrice'),
                            'in_stock': 1 if vr.get('inventoryStatusOnline') == 'inStock' else 0
                        })

            except Exception as e:
                print 'Variants Data Error: {}'.format(traceback.format_exc(e))

        return variants if len(variants) > 1 else None

    @staticmethod
    def _find_between(s, first, last, offset=0):
        try:
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""
