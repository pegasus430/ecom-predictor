import re, json

def find_between(s, first, last, offset=0):
    try:
        start = s.index(first, offset) + len(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""

class StaplesVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.page_raw_text = response.body

    def setupCH(self, page_raw_text):
        """ Call it from CH spiders """
        self.page_raw_text = page_raw_text

    def _variants(self, variants_array):
        variants = []
        for k, variant in enumerate(variants_array):
            image_url = variant.get('product', {}).get('images', {}).get('thumbnail')
            if image_url:
                image_url = image_url[0]
            in_stock_data = variant.get('inventory', {}).get('items')
            if in_stock_data:
                in_stock = in_stock_data[0].get('instock')
                if not in_stock:
                    in_stock = not in_stock_data[0].get('productIsOutOfStock', False)
            price = variant.get('price', {}).get('item')
            if price:
                price = price[0].get('nowPrice') or price[0].get('priceAfterSavings')
            upc = variant.get('product', {}).get('upcCode', None)
            if upc == '00000000000000':
                upc = None
            variants.append({
                'image_url': image_url,
                'in_stock': in_stock,
                'price': price,
                'properties': variant.get('properties', {}),
                'selected': k == 0,
                'sku_id': variant.get('itemID'),
                'upc': upc
            })

        if variants:
            return variants
