import requests
import lxml.html as html


class CrutchfieldVariants(object):
    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self):
        variants = []
        variant_links = self.tree_html.xpath('//input[@name="option"]/@data-cf-multiprod-url')
        for link in variant_links:
            r = requests.get(link, timeout=5)
            body = html.fromstring(r.content)
            variant = self._extract_variant(body)
            if variant:
                variants.append(variant)
        if len(variants) > 1:
            return variants

    def _extract_variant(self, body):
        sku = body.xpath('//span[@itemprop="sku"]/text()')
        sku = sku[0] if sku else None

        price = body.xpath('//meta[@itemprop="price"]/@content')
        try:
            price = float(price[0].replace(',', ''))
        except:
            price = None

        try:
            label = body.xpath('//label[@for="' + sku + '"]')[0]
            name = label.xpath('span[@class="variation"]/text()')
            if not name:
                name = label.xpath('text()')
            name = name[0]
        except:
            name = None

        oos = body.xpath('//div[contains(@class, "buyBoxContainer")]//span[contains(@class, "stock-out")]')
        oos = bool(oos)

        if name:
            return {
                name:
                    {
                        'price': price,
                        'sku': sku,
                        'in_stock': not oos
                    }
            }
