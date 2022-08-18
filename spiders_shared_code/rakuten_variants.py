import lxml.html
# import requests
import re
from urlparse import urljoin


class RakutenVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html, product_page_url):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.product_page_url = product_page_url

    def _variants(self):
        try:
            in_stock_variations = {}
            out_of_stock_variations = []
            for variation_type in self.tree_html.xpath('//*[@data-variation-type]'):
                variation_type_name = variation_type.xpath('@data-variation-type')[0]
                for swatch in variation_type.xpath('*//li/a[@data-name]'):
                    swatch_value = swatch.xpath('@data-name')[0]
                    # Variation Sku
                    try:
                        skuId = re.search('skuId=(.*)', swatch.xpath('@data-refresh-url')[0]).group(1)
                        # Get variations of default skelt
                        vr = in_stock_variations.get(skuId, {'skuId': skuId,
                                                             'properties':{},
                                                             'url':urljoin(self.product_page_url, swatch.xpath('@href')[0]),
                                                             'in_stock': True})
                        # Update propierties
                        properties = vr.get('properties',{})
                        properties[variation_type_name.lower()] = swatch_value
                        vr['properties'] = properties
                        in_stock_variations[vr['skuId']] = vr
                    except:
                        out_of_stock_variations.append({'properties':{variation_type_name:swatch_value}, 'in_stock': False})

            return in_stock_variations.values() + out_of_stock_variations

        except:
            pass

