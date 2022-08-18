import lxml.html


class OrientaltradingVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self):
        variants = []
        for color in self.tree_html.xpath(
                '//*[contains(@class, "pd-attributes-box")]'
                '//fieldset[contains(@class, "select-options")]'
                '//select/option/text()'):
            if color.lower().strip() == 'color':
                continue
            variants.append({
                'in_stock': None,
                'price': None,
                'properties': {u'color': u'%s' % color.strip()},
                'selected': None,
                'url': None})
        return variants if variants else None