import re
import lxml.html

class OcadoVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    @staticmethod
    def _parse_variants(tree_html):
        for option in tree_html.xpath('//form[contains(@action, "resolveDerivative")]//option[@value != "-1"]'):
            option_name = option.xpath('./parent::select/@name')
            url = option.xpath('./@data-href')
            value = option.xpath('./text()')
            selected = bool(option.xpath('./@selected'))
            if all([option_name, url, value]):
                yield {'option_name': option_name[0], 'url': url[0], 'value': value[0], 'selected': selected}

    @staticmethod
    def _parse_sku(url):
        sku = re.search(r'/(\d+)\?', url)
        return sku.group(1) if sku else None

    @staticmethod
    def _parse_variant_price(tree_html, sku):
        price_data = tree_html.xpath(
            '//div[contains(@class, "price-{sku}")]//meta[@itemprop="price"]/@content'.format(sku=sku)
        )
        if price_data:
            price = re.search(r'\d+(?:.\d+)?', price_data[0])
            return float(price.group()) if price else None

    @staticmethod
    def _parse_in_stock(tree_html):
        return bool(tree_html.xpath('//meta[@itemprop="availability" and contains(@content, "InStock")]'))

    def _variants(self):
        variants = []
        for variant in self._parse_variants(self.tree_html):
            sku_id = self._parse_sku(variant['url'])
            if sku_id:
                variants.append({
                    'in_stock': self._parse_in_stock(self.tree_html),
                    'price': self._parse_variant_price(self.tree_html, sku_id),
                    'properties': {variant['option_name']: variant['value']},
                    'selected': variant['selected'],
                    'sku_id': sku_id
                })
        return variants if variants else None
