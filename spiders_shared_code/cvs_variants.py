import re

class CvsVariants(object):

    def setupSC(self, product_json, selected_sku):
        """ Call it from SC spiders """
        self.product_json = product_json
        self.selected_sku = selected_sku

    def setupCH(self, product_json, selected_sku):
        """ Call it from CH spiders """
        self.product_json = product_json
        self.selected_sku = selected_sku

    def _variants(self):
        variants = []

        dropdown_field = self.product_json['gbi_Variant_Dropdown_Field']

        for variant_json in self.product_json['variants']:
            variant = {
                'image_url': variant_json['subVariant'][0]['BV_ImageUrl'],
                'properties': {},
                'price': float(variant_json['subVariant'][0]['gbi_Actual_Price']),
                'selected': variant_json['subVariant'][0]['p_Sku_ID'] == self.selected_sku
            }

            for k, v in variant_json.iteritems():
                if k == dropdown_field:
                    property_name = re.search('p_Sku_(.*)', k).group(1)
                    variant['properties'][property_name] = v
                    break

            variants.append(variant)

        if len(variants) > 1:
            return variants
