import lxml.html

class Bushfurniture2goVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self):
        variants = []
        price_block = self.tree_html.xpath(
            '//div[contains(@class, "pdp-product-info")]'
            '//div[@class="product-price"]//span/text()'
        )

        try:
            price = float(price_block[0].replace('$', '')) if price_block else None
        except:
            price = None

        for color in self.tree_html.xpath('//select[@id="ctl00_mainPlaceHolder_ddlOptions"]//option/text()'):
            variants.append({
                'price': price,
                'properties': {
                    'color': color,
                },
                'in_stock': price != None,
            })

        return variants if variants else []
