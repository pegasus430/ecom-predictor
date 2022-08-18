import re
import traceback

try:
    from scrapy import log
    scrapy_imported = True
except:
    scrapy_imported = False

class DebenhamsVariants(object):

    def setupSC(self, varints):
        """ Call it from SC spiders """
        self.variants = varints

    def _variants(self):
        variant_list = []
        for item in self.variants:
            variant = {}
            variant["in_stock"] = item.get('stocklevel', '') != 'oos'
            price = item.get('prices', {}).get('current')
            try:
                price = re.search(r'(\d+[\.]\d*)', price)
                variant['price'] = float(price.group(1))
            except:
                if scrapy_imported:
                    log.msg("Error Parsing Variant Price: {}".format(traceback.format_exc()))
            variant['properties'] = {}
            variant['properties']['color'] = item.get('colour')
            for key, property in item.get('productoptions', {}).iteritems():
                variant['properties'][key] = property.get('value')
            variant_list.append(variant)
        if variant_list:
            return variant_list
