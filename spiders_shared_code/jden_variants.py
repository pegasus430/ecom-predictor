import lxml.html
from itertools import product as itertools_product


class JdVariants(object):
    def setupSC(self, response):
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        self.tree_html = tree_html

    def _variants(self):
        options = self.tree_html.cssselect('ul.saleAttr')
        variants_initial = {}
        for option in options:
            option_name = option.xpath('../preceding-sibling::'
                                       'div[@class="dt"]/text()')[0]
            values = option.xpath('li/a/@title | li[not(a)]/text()')
            variants_initial[option_name] = values
        variant_names = variants_initial.keys()
        variant_values = list(itertools_product(*variants_initial.itervalues()))
        variants = []
        for variant_value in variant_values:
            properties = {}
            for i, v in enumerate(variant_value):
                properties[variant_names[i]] = v
            data = dict(price=None, selected=None, properties=properties)
            variants.append(data)
        return variants
