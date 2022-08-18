import json

import lxml.html

class JohnLewisVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self, product_page_url):
        variants = []
        canonical_url = product_page_url.split("?")[0] if product_page_url else ""
        color_selectors = self.tree_html.xpath('.//*[@id="prod-product-colour"]//li')
        sizes_selectors = self.tree_html.xpath('.//*[@id="prod-product-size"]//li')
        if color_selectors and not sizes_selectors:
            sizes_selectors = ["placeholder_size"]
        for color in color_selectors:
            for size in sizes_selectors:
                variant = {}
                price = color.xpath("./@data-jl-price")
                variant['price'] = float(price[0].replace("&pound;", "")) if price else None
                selected = color.xpath("./@class")[0]
                variant['selected'] = True if "selected" in ''.join(selected) else False
                props = {}
                col = color.xpath('.//img/@title')
                props['color'] = col[0] if col else None
                if not size == 'placeholder_size':
                    siz = size.xpath("./@data-jl-size")
                    props['size'] = siz[0] if siz else None
                    url = "{}?selectedSize={}&colour={}&isClicked=true".format(canonical_url, props['size'],
                                                                               props['color'])
                else:
                    url = "{}?colour={}&isClicked=true".format(canonical_url, props['color'])
                variant['url'] = url
                variant['properties'] = props
                if not size == 'placeholder_size' and variant.get("selected"):
                    oos = size.xpath("./@class")
                else:
                    oos = color.xpath("./@class")
                in_stock = oos[0] if oos else None
                variant["in_stock"] = False if "out-of-stock" in in_stock else True
                variants.append(variant)
        if variants:
            return variants