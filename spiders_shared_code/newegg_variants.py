import json
import traceback
import itertools

class NeweggVariants(object):
    def setupSC(self, response):
        """ Call it from SC spiders """
        self.body = response.body

    def setupCH(self, body):
        """ Call it from CH spiders """
        self.body = body

    def _variants(self):
        product_property = self._find_between(self.body, 'properties: ', '],')
        try:
            data = json.loads(product_property + ']')
            attribute_list = []
            values_list = []
            for datum in data:
                value_list = []
                attribute_list.append(datum.get('description'))
                for item in datum.get('data', []):
                    value_list.append(item.get('description'))
                values_list.append(value_list)

            combine_list = list(itertools.product(*values_list))
            variant_list = []
            for item in combine_list:
                variant = {
                    'properties': {}
                }
                for idx, attribute in enumerate(attribute_list):
                    variant['properties'][attribute] = item[idx]
                variant_list.append(variant)
            return variant_list if variant_list else None
        except:
            print "Parsing Error Variants: {}".format(traceback.format_exc())

    def _find_between(self, s, first, last, offset=0):
        try:
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""
