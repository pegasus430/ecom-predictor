from lxml import html


class VitacostVariants(object):

    def setupSC(self, response):
        self.response = response
        self.tree_html = html.fromstring(response.body)

    def setupCH(self, tree_html):
        self.tree_html = tree_html

    def _variants(self):
        variants = []

        properties = self.tree_html.xpath("//ul[@id='pdpVariations']//select//option")
        property_name = self.tree_html.xpath("//ul[@id='pdpVariations']//label/text()")
        if property_name:
            property_name = property_name[0].replace(':', '').lower()
        else:
            property_name = 'size'

        for property in properties:
            value = property.xpath("./text()")
            selected = property.xpath("./@selected")
            if value:
                variants.append({
                    'selected': bool(selected),
                    'properties': {
                        property_name: value[0]
                    }
                })

        return variants if variants else None
