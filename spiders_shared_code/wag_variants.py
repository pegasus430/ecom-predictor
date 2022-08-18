import lxml.html
import re

class WagVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)
        self.url = response.url

    def setupCH(self, tree_html, url):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.url = url

    def _find_between(self, s, first, last):
        try:
            start = s.index(first) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""

    def _variants(self):
        variants = []
        try:
            for item in self.tree_html.xpath('//*[@class="diaperItemTR"]'):
                vr = {}
                vr['in_stock'] = not bool(
                    item.xpath('./td[@class="outOfStockQty"]'))
                price = item.xpath(
                    './/*[@class="autoShipNormal"]'
                    '/*[@class="normalPrice" or @class="salePrice"]/text()')[0]

                price = re.findall('[\d\.]+', price)

                if price:
                    vr['price'] = price[0]
                images = ['http:' + x for x in item.xpath('.//img/@src')]
                if images:
                    vr['image_url'] = images[0]
                sku = item.xpath('td/@sku')
                if sku:
                    vr['skuId'] = sku[0]
                primary = item.xpath('@isprimarysku')[0]
                selected = primary == 'Y'
                vr['selected'] = selected
                if sku:
                    url = re.sub('(sku=)(.+?)&', '\g<1>%s&' % sku[0], self.url)
                    vr['url'] = url

                variants.append(vr)

            return variants if variants and len(variants) > 1 else None
        except:
            import traceback
            print traceback.print_exc()

    def _swatches(self):
        swatches = []
        color_swatches = self.tree_html.xpath('//div[@class="colorPaneItems"]')
        for swatch in color_swatches:
            swatch_info = {}
            swatch_info["swatch_name"] = "color"
            swatch_info["color"] = swatch.xpath('div/@color')[0]
            swatches.append(swatch_info)

        return swatches if swatches else []
