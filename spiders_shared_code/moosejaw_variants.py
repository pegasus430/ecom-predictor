import itertools

class MoosejawVariants(object):

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def swatches(self):
        swatches = []

        image_colors = self.tree_html.xpath("//div[contains(@class, 'js-color-name')]/text()")

        image_urls = ['https:' + image_url.split('?')[0]
                for image_url in
                self.tree_html.xpath("//div[@class='alt-color-img-box']//img/@src")]

        for image_color, image_url in zip(image_colors, reversed(image_urls)):
            swatch = {
                'color': image_color,
                'hero': 1,
                'hero_image': [image_url]
            }
            swatches.append(swatch)

        return swatches if swatches else None

    def _variants(self):
        variants = []

        colors = self.tree_html.xpath("//div[contains(@class, 'js-color-name')]/text()")
        sizes = self.tree_html.xpath("//span[contains(@class, 'js-size-name')]/text()")

        if colors and sizes:
            for color in colors:
                for size in sizes:
                    variant = {
                        'properties': {
                            'color': color,
                            'size': size,
                        }
                    }
                    variants.append(variant)
        elif colors:
            for color in colors:
                    variant = {
                        'properties': {
                            'color': color,
                        }
                    }
                    variants.append(variant)
        elif sizes:
            for size in sizes:
                    variant = {
                        'properties': {
                            'size': size,
                        }
                    }
                    variants.append(variant)

        return variants if variants else None
