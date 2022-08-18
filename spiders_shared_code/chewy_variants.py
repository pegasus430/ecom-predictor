import re
import json
import lxml.html

class ChewyVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _get_variants_json(self):
        data = re.search(r'itemData\s=\s({[^;]*});', lxml.html.tostring(self.tree_html), re.DOTALL)
        if data:
            data = data.group(1).replace("'", '"')
            data = re.sub('(\w+):', r'"\1":', data)
            data = re.sub(',\s+\]', ']', data)
            data = re.sub(r'"https?"', 'https', data)
            return json.loads(data)

    @staticmethod
    def _get_price(price_str):
        price = re.search(r'[\d.]+', price_str)
        return float(price.group()) if price else None

    def _variants(self):
        variants = []
        variants_json = self._get_variants_json()
        option_name = self.tree_html.xpath(
            '//div[contains(@id, "variation-")]/@dim-identifier'
        )
        options = self.tree_html.xpath(
            '//ul[@class="variation-selector"]//li'
        )
        in_stock = self.tree_html.xpath('//div[@id="availability"]/span/text()')[0] == 'In stock'
        selected = self.tree_html.xpath('//input[@id="itemId"]/@value')
        if option_name and options:
            for i,option in enumerate(options):
                key = variants_json.keys()[len(options) - i - 1]

                item = variants_json[key]
                variants.append(
                    {
                        'properties':
                            {
                                option_name[0]: option.xpath('./span/text()')[0]
                            },
                        'price': self._get_price(item['price']),
                        'sku_id': item['sku'],
                        'selected': 'selected' in option.xpath('./@class')[0]
                    }
                )
        return variants if variants else None