import json
import re
import lxml.html
import requests

try:
    from scrapy import log
    scrapy_imported = True
except:
    scrapy_imported = False


class LeviCaVariants(object):

    local_variants_map = {}  # used to filter unique results (by `properties`)

    VARIANT_URL = "https://www.levi.com/CA/en_CA/p/{sku}/data"

    def setupSC(self, response, ignore_color_variants):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)
        self.ignore_color_variants = ignore_color_variants
        self.product_page_url = response.url

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _extract_swatches(self):
        try:
            buy_stack_json_text = re.search('"swatches" : (.*?)}]', lxml.html.tostring(self.tree_html))
            buy_stack_json = json.loads(buy_stack_json_text.group(1) + '}]')
        except Exception as e:
            if scrapy_imported:
                log.msg("Failed extracting json block with regex: {}".format(e))
            buy_stack_json = None
        return buy_stack_json

    @staticmethod
    def _extract_colors(data):
        """
        Filter colors by page layout
        """
        result = {}
        for color_data in data:
            color_id = color_data.get('code', '')
            color_name = color_data.get('colorName', '')
            result[color_id] = color_name
        return result

    @staticmethod
    def _extract_sizes(data):
        """
        Filter colors by page layout
        """
        result = []
        for size_data in data.get('variantOptions', []):
            result.append(size_data.get('displaySizeDescription', ''))
        return result

    def _variants(self):
        variants = []
        colors = self._extract_colors(self._extract_swatches())
        color_ids = colors.keys()
        for color_id in color_ids:
            product_json = requests.get(self.VARIANT_URL.format(sku=color_id)).json()
            link = 'https://www.levi.com/CA/en_CA' + product_json.get('url', '')
            url = re.sub(r'(\d+)$', color_id, link)
            product_body = requests.get(url).content
            price = re.search('"value":((\d+)\.(\d+))', product_body)
            price = price.group(1) if price else None
            size_list = self._extract_sizes(product_json)
            product = None

            for size in size_list:
                for prod in product_json.get('variantOptions', []):
                    if prod.get('displaySizeDescription') == size:
                        product = prod
                        break
                if product:
                    stock_level = product.get('stock', {}).get('stockLevel', '')
                else:
                    stock_level = None
                variant = {
                    'reseller_id': color_id,
                    'url': url,
                    'in_stock': False if stock_level == 0 else True,
                    'price': price,
                    'colorid': color_id,
                    'properties': {},
                    'selected': True if color_id in self.product_page_url else False,
                }
                if size:
                    variant['properties']['size'] = size
                if color_id:
                    variant['properties']['color'] = colors.get(color_id)
                variants.append(variant)
        return variants

    def _swatches(self):
        buy_stack_json = self._extract_swatches()

        if buy_stack_json:
            swatch_list = []

            for swatch in buy_stack_json:
                swatch_info = {}
                swatch_info["swatch_name"] = "color"
                swatch_info["color"] = swatch.get('colorName')
                swatch_info["hero"] = 1
                swatch_info["thumb"] = 1
                swatch_info["hero_image"] = swatch.get('imageUrl')
                swatch_info["thumb_image"] = swatch.get('imageUrl')
                swatch_list.append(swatch_info)

            if swatch_list:
                return swatch_list

        return None
