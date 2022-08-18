import lxml.html
from itertools import product
import json
from lxml import html


class HouseOffRaserVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _find_between(self, s, first, last):
        try:
            start = s.index(first) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""

    def _variants(self):
        """
        Parses variants using RegExp from HTML body
        """
        variation_json_text = self._find_between(html.tostring(self.tree_html), "var variations = (", ").variations;").strip()

        if variation_json_text:
            variants = []
            try:
                data = json.loads(variation_json_text)
            except ValueError as exc:
                return None

            variations = data.get('variations')

            if variations:
                for variation in variations.itervalues():
                    for size in variation['lsizes']:
                        properties = {
                            'color': variation['colourname'],
                            'size': size
                        }

                        size_info = variation['sizes'].get(size)
                        if size_info:
                            stock = size_info.values()[0]
                            out_of_stock = stock != 'true'

                            size_id = variation['sizes'][size].keys()[0]  # Size variant id
                            price = float(variation['priceValues'][size_id])
                        else:
                            out_of_stock = True
                            price = product['price'].price.__float__()

                        single_variant = {
                            'out_of_stock': out_of_stock,
                            'price': format(price, '.2f'),
                            'properties': properties
                        }

                        variants.append(single_variant)

                return variants
        else:
            return None
