from lxml import html
import re


class OldnavyVariants(object):
    color_info = []

    def setupSC(self, response, product_json):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = html.fromstring(response.body)
        self.product_json = product_json

    def setupCH(self, tree_html, product_json):
        """ Call it from CH spiders """
        self.tree_html = tree_html
        self.product_json = product_json

    def swatches(self):
        site_domain = 'http://oldnavy.gap.com'
        swatches = []

        for variant in self.product_json.get('variants', []):
            for product_style_colors in variant.get('productStyleColors', []):
                for swatch in product_style_colors:
                    swatches.append({
                        'color': swatch['colorName'],
                        'hero': 1,
                        'hero_image': site_domain + swatch['largeImagePath'],
                    })

        if swatches:
            return swatches

    def _variants(self):
        if not self.product_json:
            return None

        variants = []
        full_sizes_list = []
        raw_variants = self.product_json.get('variants', [])

        for raw_variant in raw_variants:
            variant_name = raw_variant.get('name')
            colors = raw_variant.get('productStyleColors', [])

            dimensions1 = raw_variant.get('sizeDimensions', {}).get('sizeDimension1', {}).get('dimensions', [])
            dimensions2 = raw_variant.get('sizeDimensions', {}).get('sizeDimension2', {}).get('dimensions', [])

            if not dimensions2:
                full_sizes_list = dimensions1
            else:
                for first_size in dimensions1:
                    for second_size in dimensions2:
                        full_sizes_list.append(' x '.join([first_size, second_size]))

            sizes_list = list(full_sizes_list)

            for color_group in colors:
                for color in color_group:
                    full_sizes_list = list(sizes_list)
                    self.color_info.append(color)
                    color_name = color.get('colorName')
                    try:
                        price = color.get('localizedCurrentPrice')
                        price = re.findall(r'[\d\.\,]+', price)[0]
                        price = round(float(price.replace(',','.')), 2)
                    except:
                        price = 0
                    sizes = color.get('sizes', [])

                    for size in sizes:
                        sku = size.get('skuId')
                        in_stock = size.get('inStock')
                        size_dimension1 = size.get('sizeDimension1')
                        size_dimension2 = size.get('sizeDimension2')

                        if size_dimension2:
                            size_dimension = ' x '.join([size_dimension1, size_dimension2])
                        else:
                            size_dimension = size_dimension1

                        if size_dimension in full_sizes_list:
                            full_sizes_list.remove(size_dimension)

                        variant = {
                                    'properties': {
                                        'variant_name': variant_name,
                                        'color': color_name,
                                        'size': size_dimension
                                    },
                                'sku': sku,
                                'price': price,
                                'in_stock': in_stock
                        }
                        variants.append(variant)
        return variants
