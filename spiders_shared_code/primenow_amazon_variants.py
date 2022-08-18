
import re
import lxml.html
import json
import itertools

from lxml import html, etree


class PrimenowAmazonVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self):
        variants = []
        try:
            canonical_link = self.tree_html.xpath("//link[@rel='canonical']/@href")
            original_product_canonical_link = canonical_link[0] if canonical_link else None
            variants_json_data = self.tree_html.xpath(
                '''.//script[contains(text(),
                "P.register('twister-js-init-mason-data")]/text()'''
            )[0]

            variants_json_data = re.findall('var\s?dataToReturn\s?=\s?({.+});', variants_json_data, re.DOTALL)
            cleared_vardata = variants_json_data[0].replace("\n", "")
            cleared_vardata = re.sub("\s\s+", "", cleared_vardata)
            cleared_vardata = cleared_vardata.replace(',]', ']').replace(',}', '}')
            variants_data = json.loads(cleared_vardata)

            all_variations_array = variants_data.get("dimensionValuesData", [])
            all_combos = list(itertools.product(*all_variations_array))
            all_combos = [list(a) for a in all_combos]
            asin_combo_dict = variants_data.get("dimensionValuesDisplayData", {})
            props_names = variants_data.get("dimensionsDisplay", [])
            instock_combos = []
            all_asins = []
            # Fill instock variants
            for asin, combo in asin_combo_dict.items():
                all_asins.append(asin)
                instock_combos.append(combo)
                variant = {}
                variant["asin"] = asin
                properties = {}
                for index, prop_name in enumerate(props_names):
                    properties[prop_name] = combo[index]
                variant["properties"] = properties
                variant["in_stock"] = True
                variants.append(variant)
                if original_product_canonical_link:
                    variant["url"] = "/".join(original_product_canonical_link.split("/")[:-1]) + "/{}".format(asin)
                else:
                    variant["url"] = "/".join(self.product_url.split("/")[:-1]) + "/{}".format(asin)

            # Fill OOS variants
            oos_combos = [c for c in all_combos if c not in instock_combos]
            for combo in oos_combos:
                variant = {}
                properties = {}
                for index, prop_name in enumerate(props_names):
                    properties[prop_name] = combo[index]
                variant["properties"] = properties
                variant["in_stock"] = False
                variants.append(variant)
            # Price for variants is extracted on SC - scraper side, maybe rework it here as well?
        except Exception as e:
            print 'Error extracting v2 variants:', e
        return variants
