import re
import json
import traceback
import itertools

from scrapy import Request
from scrapy.log import WARNING
from collections import OrderedDict

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider,
                                     cond_set_value, FormatterWithDefaults)

class ShopNordstromProductsSpider(BaseProductsSpider):
    name = 'shopnordstrom_products'
    allowed_domains = ["shop.nordstrom.com", "nordstrom.ugc.bazaarvoice.com"]

    SEARCH_URL = 'http://shop.nordstrom.com/api/sr/{search_term}?' \
                 'page={page}&sort={sort}'

    REVIEWS_URL = 'http://nordstrom.ugc.bazaarvoice.com/4094redes/' \
                  '{}/reviews.djs?format=embeddedhtml'

    ITEM_URL = 'http://shop.nordstrom.com/s/{}'

    SORT_MODES = {
        'featured': 'Boosted',
        'price_asc': 'PriceLowToHigh',
        'price_desc': 'PriceHighToLow',
        'newest': 'Newest',
        'sale': 'Sale',
        'rating': 'CustomerRating'
    }

    def __init__(self, sort_mode='featured', *args, **kwargs):
        if sort_mode not in self.SORT_MODES:
            sort_mode = 'featured'
        self.SORTING = self.SORT_MODES[sort_mode.lower()]
        self.br = BuyerReviewsBazaarApi(called_class=self)
        super(ShopNordstromProductsSpider, self).__init__(
                url_formatter=FormatterWithDefaults(page=1, sort=self.SORTING),
                site_name=self.allowed_domains[0],
                *args, **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def start_requests(self):
        for item in super(ShopNordstromProductsSpider, self).start_requests():
            yield item.replace(headers={'Accept': 'application/json'})

    def parse_product(self, response):
        product = response.meta['product']

        try:
            product_info = re.search('ProductDesktop, ({.*})', response.body)
            content = json.loads(product_info.group(1))
        except Exception:
            self.log('Error while parsing json: {}'.format(traceback.format_exc()), WARNING)

            product['not_found'] = True
            product['no_longer_available'] = True
            return product

        data = content.get('initialData', {}).get('Model', {}).get('StyleModel', {})

        title = data.get('Name')
        cond_set_value(product, 'title', title)

        brand = data.get('Brand', {}).get('Name')
        if not brand:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        description = data.get('Description')
        cond_set_value(product, 'description', description)

        price_data = data.get('Price')
        if price_data:
            price = price_data.get('CurrentMinPrice', 0)
            currency = price_data.get('CurrencyCode', 'USD')
            price = Price(price=price, priceCurrency=currency)
            special_pricing = price_data.get('DisplayType') == 'Sale'
            cond_set_value(product, 'price', price)
            cond_set_value(product, 'special_pricing', special_pricing)

        default_media = data.get('DefaultMedia', {})
        if default_media:
            img = default_media.get('ImageMediaUri', {}).get('Zoom')
            cond_set_value(product, 'image_url', img)

        is_out_of_stock = not data.get('IsAvailable')
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        categories = [cat.get('Text') for cat
                      in content.get('initialData', {}).get('Breadcrumbs', [])]
        if categories:
            cond_set_value(product, 'categories', categories[1:])
            cond_set_value(product, 'department', categories[-1])

        cond_set_value(product, 'locale', 'en_US')

        variants = self._parse_variants(data)
        if variants:
            sku = variants[0].get('properties', {}).get('sku')
            cond_set_value(product, 'sku', sku, conv=unicode)
            if len(variants) == 1:
                variants = None
        cond_set_value(product, 'variants', variants)

        product_id = data.get('BazaarvoiceStyleId')
        cond_set_value(product, 'reseller_id', product_id)
        if product_id:
            return Request(self.REVIEWS_URL.format(product_id),
                           self.br.parse_buyer_reviews,
                           meta={'product': product})

        return product

    def _parse_variants(self, data):
        groups = data.get('ChoiceGroups')
        if not groups:
            return

        items = data.get('Skus')
        variants = []
        found_variants = []
        properties = {k: v for k, v in groups[0].iteritems() if type(v) == list}
        for item in items:
            variant = {'properties': {}}
            sku_id = item.get('RmsSkuId')
            variant['in_stock'] = item.get('IsAvailable')
            price = re.search(r'\d*\.\d+|\d+', item.get('Price', ''))
            if price:
                price = price.group()
                variant['price'] = float(price)

            for name in properties.iterkeys():
                value = item.get(name)
                variant['properties'][name] = value
            found_variants.append(set(variant['properties'].itervalues()))
            variant['properties']['sku'] = sku_id
            variants.append(variant)

        properties_dict = {}
        for name, options in properties.iteritems():
            for option in options:
                value = option.get('Value')
                properties_dict[value] = name

        # out of stock variants
        for options in itertools.product(*properties.itervalues()):
            props = set()
            for option in options:
                props.add(option.get('Value'))
            if props not in found_variants:
                properties = {}
                for prop in props:
                    key = properties_dict.get(prop)
                    if key:
                        properties[key] = prop
                variants.append({'properties': properties, 'in_stock': False})

        return variants

    def _scrape_total_matches(self, response):
        totals = re.search('"TotalHits":(\d+)', response.body)
        return int(totals.group(1)) if totals else 0

    def _scrape_product_links(self, response):
        try:
            js = json.loads(response.body_as_unicode(),
                            object_pairs_hook=OrderedDict)
        except ValueError:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
            return

        items = js.get('Products', [])
        for item in items:
            yield self.ITEM_URL.format(item), SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        try:
            js = json.loads(response.body_as_unicode()).get('Pagination', {})
        except ValueError:
            return
        current_page = js.get('Page')
        max_per_page = js.get('Top')
        totals = js.get('TotalHits')

        try:
            max_page = round(totals / max_per_page)
        except:
            max_page = None

        if not current_page or not max_page or current_page >= max_page:
            return

        search_term = response.meta.get('search_term')
        url = self.url_formatter.format(self.SEARCH_URL, sort=self.SORTING,
                                        search_term=search_term, page=current_page + 1)
        headers = {'Accept': 'application/json'}
        meta = dict((k, v) for k, v in response.meta.iteritems()
            if k in ['remaining', 'total_matches', 'search_term',
                'products_per_page', 'scraped_results_per_page']
        )
        return Request(url, headers=headers, meta=meta)
