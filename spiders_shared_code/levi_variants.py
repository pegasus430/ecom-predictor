# -*- coding: utf-8 -*-

import itertools
import json
import re
import traceback
import lxml.html

try:
    from scrapy import log

    scrapy_imported = True
except:
    scrapy_imported = False


class LeviVariants(object):
    local_variants_map = {}  # used to filter unique results (by `properties`)
    i18n_actual = [u"now", u"aktuell", u"à présent"]
    i18n_onesize = [u"One Size", u"Taille unique", u"Einheitsgröße"]

    def setupSC(self, response, ignore_color_variants):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body_as_unicode())
        self.ignore_color_variants = ignore_color_variants

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _find_between(self, s, first, last):
        try:
            start = s.index(first) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""

    def _find_variant_with_better_data(self, v1, v2):
        if v1.get('url', None) and not v2.get('url', None):
            return v1
        else:
            return v2

    def _extract_buy_stack_json(self):
        try:
            js_block = self.tree_html.xpath(
                "//script[@type='text/javascript' and contains(text(), 'buyStackJSON')]/text()")
            js_block = js_block[0] if js_block else ""
            json_regex = r"var\s?buyStackJSON\s?=\s?[\'\"](.+)[\'\"];?\s?"
            json_regex_c = re.compile(json_regex)
            buy_stack_json_text = json_regex_c.search(js_block)
            buy_stack_json_text = buy_stack_json_text.groups()[0] if buy_stack_json_text else ""
            buy_stack_json_text = buy_stack_json_text.replace("\'", '"').replace('\\\\"', "")
            buy_stack_json = json.loads(buy_stack_json_text)
        except Exception as e:
            if scrapy_imported:
                log.msg("Failed extracting json block with regex: {}".format(e))
            buy_stack_json = None
        return buy_stack_json

    def _variants(self):
        buy_stack_json = self._extract_buy_stack_json()
        if buy_stack_json:
            canonical_link = self.tree_html.xpath("//link[@rel='canonical']/@href")
            canonical_link = canonical_link[0] if canonical_link else ''

            is_color_showed = bool(
                self.tree_html.xpath("//div[@id='main-pdp-container']//div[@class='color']"))
            is_size_showed = bool(
                self.tree_html.xpath('//div[@class="pdp-sizes pdp-size-sizes"]//a[@class="size-swatch"]'))
            is_waist_showed = bool(
                self.tree_html.xpath("//div[@id='main-pdp-container']//div[contains(@class, 'pdp-waist-sizes')]"))
            is_length_showed = bool(
                self.tree_html.xpath("//div[@id='main-pdp-container']//div[contains(@class, 'pdp-length-sizes')]"))

            only_size = is_size_showed and not (is_waist_showed or is_length_showed)
            length_waist_available = is_waist_showed and is_length_showed
            colors = self._extract_colors(buy_stack_json, only_size, length_waist_available)

            try:
                default_color = self.get_default_color_name()
                if self.ignore_color_variants:
                    colors = {key: value for key, value in colors.items() if value == default_color[0]}
            except:
                if scrapy_imported:
                    log.msg("Can't get default color: {}- continue with full color set".format(traceback.format_exc()))

            # empty str in list in purpose to build unique_number
            color_ids = colors.keys() if is_color_showed else ['']

            waist_list = buy_stack_json.get('attrs', {}).get('waist', []) if is_waist_showed else ['']
            size_list = buy_stack_json.get('attrs', {}).get('size', []) if is_size_showed else ['']
            length_list = buy_stack_json.get('attrs', {}).get('length', []) if is_length_showed else ['']

            variants = []
            products = buy_stack_json.get('sku', {})

            for color_id, waist, size, length in itertools.product(color_ids, waist_list, size_list, length_list):
                # it's a key in sku dict
                size = 'OS' if size in self.i18n_onesize else size

                url = re.sub(r'(\d+)$', color_id, canonical_link)
                product = [product for product in products.values() if product.get('colorid', '') == color_id
                           and product.get('size', '') == size
                           and product.get('length', '') == length
                           and product.get('waist', '') == waist]
                product = product[0] if product else {}
                if product:
                    in_stock = bool(product.get('stock'))
                    price = self._extract_price(product)
                else:
                    in_stock = False
                    price = None

                variant = {
                    'reseller_id': color_id,
                    'url': url,
                    'upc': product.get('ean'),
                    'in_stock': in_stock,
                    'price': price,
                    'properties': {},
                    'selected': False,
                    'colorid': color_id

                }
                if color_id:
                    variant['properties']['color'] = colors.get(color_id)
                if waist:
                    variant['properties']['waist'] = waist
                if size:
                    variant['properties']['size'] = size if size != 'OS' else 'One size'
                if length:
                    variant['properties']['length'] = length

                variants.append(variant)

            return variants

        return []

    def get_default_color_name(self):
        default_color = self.tree_html.xpath('//div[@class="color-name"]/*/text()')
        return default_color

    def _extract_price(self, product):
        try:
            # extract sale price if available
            price = [price for price in product.get('price')
                     if price.get('il8n') in self.i18n_actual][0].get('amount', '').replace(',', '.')
            price = float(re.findall('\d*\.\d+|\d+', price)[0])
        except Exception as ex:
            if scrapy_imported:
                log.msg("Can't extract price: {}".format(ex))
            price = None
        return price

    @staticmethod
    def _extract_colors(data, only_size, length_waist_available):
        """
        Filter colors by page layout
        """
        result = {}
        colors_data = data.get('colorid', {}).values()
        for color_data in colors_data:
            only_size_color = color_data.get('onlySize')
            length_waist_available_color = color_data.get('lengthWaistAvailable')

            if only_size_color == only_size and length_waist_available_color == length_waist_available:
                color_id = color_data.get('colorid', '')
                color_name = color_data.get('finish', {}).get('title', '')
                result[color_id] = color_name
        return result

    def _swatches(self):
        buy_stack_json = None

        try:
            buy_stack_json_text = self._find_between(
                " ".join(self.tree_html.xpath("//script[@type='text/javascript']/text()")), "var buyStackJSON = '",
                "'; var productCodeMaster =").replace("\'", '"').replace('\\\\"', "")
            buy_stack_json = json.loads(buy_stack_json_text)
        except:
            buy_stack_json = None

        if buy_stack_json:
            swatch_list = []

            for swatch in buy_stack_json["colorid"]:
                swatch_info = {}
                swatch_info["swatch_name"] = "color"
                swatch_info["color"] = buy_stack_json["colorid"][swatch]["finish"]["title"]
                swatch_info["hero"] = 1
                swatch_info["thumb"] = 1
                swatch_info["hero_image"] = [buy_stack_json["colorid"][swatch]["imageURL"] + altView for altView in
                                             buy_stack_json["colorid"][swatch]["altViewsMain"]]
                swatch_info["thumb_image"] = [buy_stack_json["colorid"][swatch]["swatch"]]
                swatch_list.append(swatch_info)

            if swatch_list:
                return swatch_list

        return None
