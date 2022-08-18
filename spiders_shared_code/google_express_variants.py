import lxml.html
import re

class GoogleExpressVariants(object):

    def setupSC(self, product_json, prices=[]):
        """ Call it from SC spiders """
        self.product_json = product_json
        self.prices = prices

    def setupCH(self, product_json, prices=[]):
        """ Call it from CH spiders """
        self.product_json = product_json
        self.prices = prices

    def _variants(self):
        variants = []
        if self.product_json[1][1][1][0][48][3]:
            var_data = self.product_json[1][1][1][0][48][3][0][0][1]
            prices_correct = len(self.prices) == len(self.product_json[1][1][1][0][48][3][0][0][1])
        else:
            var_data = []
        for k, data in enumerate(var_data):
            variants.append({
                'price': self.prices[k] if prices_correct else self.product_json[1][1][1][0][48][4][1],
                'properties': {
                    'size': data[0]
                },
                'image_url': data[5],
            })
        if variants:
            return variants