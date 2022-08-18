import re
import lxml.html

class JoannVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.variants = []
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.variants = []
        self.tree_html = tree_html

    def _variants(self, stocks):
        image_urls = []

        image_data = self.tree_html.xpath('//img[@class="productthumbnail"]/@data-yo-src')
        if image_data:
            for url in image_data:
                image_urls.append(url.replace(';', '&').replace('amp', ''))

        variant_html_list = self.tree_html.xpath(
            "//div[@class='variants']//div[contains(@class, 'product-variant-tile')]")

        if not self.variants:
            for img in image_urls:
                for i, variant_html in enumerate(variant_html_list):
                    sku_id = variant_html.xpath("./@data-pid")
                    sku_id = sku_id[0].strip() if sku_id else None

                    price = self.tree_html.xpath('//div[contains(@class, %s)]'
                                                 '//span[contains(@class, "standard-price")]/text()' % sku_id)
                    try:
                        price = float(re.search('\d+\.?\d*', price[0]).group())
                    except:
                        price = None

                    in_stock = stocks[i]

                    color = variant_html.xpath(".//img/@title")
                    color = color[0].strip() if color else None

                    self.variants.append({
                        'price': price,
                        'sku_id': sku_id,
                        'in_stock': in_stock,
                        'properties': {
                            'color': color,
                        },
                        'image_url': img,
                    })
        return self.variants if len(self.variants) > 1 else None
