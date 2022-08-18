# ~~coding=utf-8~~
from __future__ import division, absolute_import, unicode_literals
import json
import collections
import ast
import itertools
import re
import lxml.html
import requests
import itertools
import urlparse


class AmazonVariants(object):

    def setupSC(self, response, product_url=None):
        """ Call it from SC spiders """
        self.CH_price_flag = False
        self.response = response
        self.tree_html = lxml.html.fromstring(response.body)
        self.product_url = product_url

    def setupCH(self, tree_html, product_url=None):
        """ Call it from CH spiders """
        self.CH_price_flag = True
        self.tree_html = tree_html
        self.product_url = product_url

    def _find_between(self, s, first, last, offset=0):
        try:
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""

    def _swatches(self):
        swatch_images = []

        try:
            swatch_image_json = json.loads(self._find_between(lxml.html.tostring(self.tree_html), 'data["colorImages"] = ', ';\n'), object_pairs_hook=collections.OrderedDict)
        except:
            swatch_image_json = []

        swatch_list = []

        for swatch in swatch_image_json:
            swatch_info = {}
            swatch_info["swatch_name"] = "color"
            swatch_info["color"] = swatch
            swatch_info["hero"] = len(swatch_image_json[swatch])
            swatch_info["thumb"] = len(swatch_image_json[swatch])
            swatch_info["hero_image"] = [image["large"] for image in swatch_image_json[swatch]]
            swatch_info["thumb_image"] = [image["thumb"] for image in swatch_image_json[swatch]]
            swatch_list.append(swatch_info)

        if swatch_list:
            return swatch_list

    def _variants(self):
        variants = []
        try:
            canonical_link = self.tree_html.xpath("//link[@rel='canonical']/@href")
            original_product_canonical_link = canonical_link[0] if canonical_link else None
            variants_json_data = self.tree_html.xpath('''.//script[contains(text(), "P.register('twister-js-init-dpx-data")]/text()''')[0]
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

            # Fill in_stock variants
            for asin, combo in asin_combo_dict.items():
                all_asins.append(asin)
                instock_combos.append(combo)
                variant = {}
                variant["asin"] = asin
                properties = {}
                for index, prop_name in enumerate(props_names):
                    properties[prop_name.strip()] = combo[index].strip()
                variant["properties"] = properties
                variants.append(variant)

                if original_product_canonical_link:
                    variant["url"] = "/".join(original_product_canonical_link.split("/")[:-1]) + "/{}".format(asin)
                else:
                    variant["url"] = "/".join(self.product_url.split("/")[:-1]) + "/{}".format(asin)

            # Get prices for in_stock variants
            # Only for CH, for SC price extraction done on sc scraper side
            if self.CH_price_flag:
                v_price_map = self._get_CH_variants_price_v2(all_asins)
                for variant in variants:
                    var_asin = variant.get("asin")
                    price = v_price_map.get(var_asin)
                    if price:
                        price = (price[:-3] + price[-3:].replace(',', '.')).replace(',', '')
                        price = round(float(price[1:]), 2)
                        variant["price"] = price

            # Fill OOS variants
            oos_combos = [c for c in all_combos if c not in instock_combos]
            for combo in oos_combos:
                variant = {}
                properties = {}
                for index, prop_name in enumerate(props_names):
                    properties[prop_name.strip()] = combo[index].strip()
                variant["properties"] = properties
                variant["in_stock"] = False
                variants.append(variant)
        except Exception as e:
            print 'Error extracting v2 variants:', e
        return variants

    def _get_CH_variants_price_v2(self, all_asins):
        # Break asins into chunks of 20
        v_asin_chunks = [all_asins[i:i + 20] for i in xrange(0, len(all_asins), 20)]

        v_price_map = {}

        try:
            referer = self.product_url.split('?')[0]
            parent_asin = self.tree_html.xpath('//input[@type="hidden" and @name="ASIN"]/@value')[0]
            group_id = re.search('productGroupId=(\w+)', lxml.html.tostring(self.tree_html)).group(1)
            store_id = self.tree_html.xpath('//input[@id="storeID" and @name="storeID"]/@value')[0]

            # Get variant price info
            for chunk in v_asin_chunks:
                asins = ','.join(chunk)

                url = "https://www.amazon.com/gp/twister/dimension?asinList={a}" \
                      "&productGroupId={g}" \
                      "&storeId={s}" \
                      "&parentAsin={p}".format(a=asins, g=group_id, s=store_id, p=parent_asin)

                headers = {'Referer': referer}

                # TODO: do not use requests
                v_price_json = json.loads(requests.get(url, headers=headers, timeout=10).content)
                for v in v_price_json:
                    v_price_map[v['asin']] = v['price']
        except Exception as e:
            print 'Error extracting variant prices v2:', e
        return v_price_map

    @staticmethod
    def _get_asin_from_url(url):
        prod_id = re.findall(r'/dp?/(\w+)|product/(\w+)/', url)
        if not prod_id:
            prod_id = re.findall(r'/dp?/(\w+)|product/(\w+)', url)
        if not prod_id:
            prod_id = re.findall(r'([A-Z0-9]{4,20})', url)
        if isinstance(prod_id, (list, tuple)):
            prod_id = [s for s in prod_id if s][0]
        if isinstance(prod_id, (list, tuple)):
            prod_id = [s for s in prod_id if s][0]
        return prod_id

    def _variants_format(self):
        variants = []
        variant_sections = self.tree_html.xpath(
            '//div[@id="tmmSwatches"]//li'
        )
        for x in variant_sections:
            prop_name = x.xpath('.//a[@class="a-button-text"]/span/text()')
            selected = x.xpath('./@class')
            if selected:
                selected = ' selected' in selected[0] if selected else False
            url = None
            asin = None
            if selected:
                url = self.product_url
                asin = self._get_asin_from_url(self.product_url)
            if not url:
                url = x.xpath('.//a[@class="a-button-text"]/@href')
                if url:
                    url = urlparse.urljoin(self.product_url, url[0])
                    asin = self._get_asin_from_url(url)
            price = x.xpath('.//span[contains(text(), "EUR")]/text()')
            if price:
                price = re.search(r'\d+(?:[,\.]\d+)?', price[0])
                price = float(price.group().replace(',', '.')) if price else None
            variants.append(
                {
                    "selected": selected,
                    "properties": {
                        "format": prop_name[0] if prop_name else None,
                    },
                    "price": price,
                    "url": url,
                    "asin": asin
                }
            )
        return variants if variants else None
