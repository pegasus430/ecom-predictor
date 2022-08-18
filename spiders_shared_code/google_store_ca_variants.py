from lxml import html
import itertools

class GoogleStoreCaVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = html.fromstring(response.body)

    def _variants(self):
        variants_types = self.tree_html.xpath('//div[@class="option-group"]')
        variants_list = []
        attributes = {}
        for variant_type in variants_types:
            name = variant_type.xpath('.//div[contains(@class, "header")]/text()')
            type_id = variant_type.attrib.get('data-variation-type')
            if name and type_id:
                attributes[type_id] = name[0]

        variants_html = self.tree_html.xpath('//div[@jsname="HRjxid"]')
        for variant_html in variants_html:
            attribs = variant_html.attrib
            in_stock = attribs.get('data-availability-status') == 'In stock'
            price = attribs.get('data-price', '$0').replace(',', '').replace('$', '')
            try:
                price = float(price)
            except:
                price = 0
            image_url = attribs.get('data-image-url')
            properties_html = variant_html.xpath('.//div[@class="variation-data"]')
            properties = {}
            for property_html in properties_html:
                pt_attribs = property_html.attrib
                type_id = pt_attribs.get('data-variation-type')
                property = pt_attribs.get('data-variation-name')
                if not type_id:
                    continue
                properties[attributes[type_id]] = property
            variants_list.append({
                'image_url': image_url,
                'in_stock': in_stock,
                'price': price,
                'properties': properties
            })

        return variants_list
