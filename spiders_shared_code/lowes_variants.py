import lxml.html


class LowesVariants(object):

    def setupSC(self, response):
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        self.tree_html = tree_html

    def _variants(self):
        variants = []
        property_name = self.tree_html.xpath("//*[@class='variant-name']/text()")
        price = self.tree_html.xpath('//*[@itemprop="price"]/@content')
        if property_name:
            property_name = property_name[0].lower()

            for media in self.tree_html.xpath(".//ul[@class='list-menu']//li"):
                property_value = media.xpath('.//p[contains(@class, "ellipsis-one-line")]/text()')
                if not property_value:
                    continue

                variant = {
                    'properties': {
                        property_name: property_value[0].strip()
                    },
                    'selected': 'selected' in media.attrib.get('class'),
                    'in_stock': True,
                    'price': float(price[0]) if price else None
                }

                variants.append(variant)

        return variants if variants else None
