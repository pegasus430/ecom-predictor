import lxml.html
import re


class CrateandbarrelVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html, product_page_url):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.product_page_url = product_page_url

    def _variants(self):
        variants = {}
        variants_ = []

        selected_sku_ = re.search(r'^http://www.crateandbarrel.com/.*?/(s\d+)', self.product_page_url)
        if selected_sku_:
            selected_sku = selected_sku_.group(1)
        else:
            selected_sku = None

        colors = self.tree_html.xpath('//div[@data-matchingskus]//img[@title]')
        for color in colors:
            skus = color.xpath('./ancestor::*[@data-matchingskus][1]/@data-matchingskus')[0].split(',')
            value = color.xpath('@title')[0]
            value_image = color.xpath('@src')[0]
            for sku in skus:
                if sku not in variants:
                    variants[sku] = {}
                variants[sku]['color'] = value
                variants[sku]['thumb_image'] = value_image

        sizes = self.tree_html.xpath('//div[@data-matchingskus]//span')
        for size in sizes:
            skus = size.xpath('./ancestor::*[@data-matchingskus][1]/@data-matchingskus')[0].split(',')
            value = size.xpath('text()')[0]
            for sku in skus:
                if sku not in variants:
                    variants[sku] = {}
                variants[sku]['size'] = value

        for sku, value in variants.iteritems():
            url = re.sub(r'^(http://www.crateandbarrel.com/.*?/)[\w\d]+',
                         r'\g<1>s{}'.format(sku), self.product_page_url)
            value['sku'] = sku
            variants_.append(
                {'url': url,
                 'price': None,
                 'selected': str(sku) == str(selected_sku),
                 'properties': value,
                 }
            )

        return variants_
