from __future__ import absolute_import, division, unicode_literals

import json
import re
import traceback
import urlparse

from scrapy.http import Request

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import (FLOATING_POINT_RGEX, BaseProductsSpider,
                                     FormatterWithDefaults, cond_set,
                                     cond_set_value)


class WalGreensProductsSpider(BaseProductsSpider):
    """ walgreens.com product ranking spider

    Takes `order` argument with following possible values:

    * `relevance`
    * `top_sellers`
    * `price_asc`, `price_desc`
    * `product_name_asc`, `product_name_desc`
    * `most_reviewed`
    * `highest_rated`
    * `most_viewed`
    * `newest_arrival`

    There are the following caveats:

    * `upc`, `related_products`,`sponsored_links`  are not scraped
    * `buyer_reviews`, `price` are not always scraped

    """
    name = "walgreens_products"
    allowed_domains = ["walgreens.com", "api.bazaarvoice.com"]
    start_urls = []
    site = 'https://www.walgreens.com'
    page = 1
    SORTING = None
    SORT_MODES = {
        'relevance': 'relevance',  # default
        'top_sellers': 'Top Sellers',
        'price_asc': 'Price Low to High',
        'price_desc': 'Price High to Low',
        'product_name_asc': 'Product Name A-Z',
        'product_name_desc': 'Product Name Z-A',
        'most_reviewed': 'Most Reviewed',
        'highest_rated': 'Highest Rated',
        'most_viewed': 'Most Viewed',
        'newest_arrival': 'Newest Arrival'
    }

    SEARCH_URL = "https://customersearch.walgreens.com/productsearch/v1/products/search"

    REVIEW_API_URL = 'http://api.bazaarvoice.com/data/batch.json?' \
                     'passkey=tpcm2y0z48bicyt0z3et5n2xf&' \
                     'apiversion=5.5&' \
                     'resource.q0=products&' \
                     'filter.q0=id%3Aeq%3A{prod_id}&' \
                     'stats.q0=reviews&'

    PRICE_VARI_API_URL = "https://www.walgreens.com/svc/products" \
                         "/{prod_id}/(PriceInfo+Inventory+ProductInfo+ProductDetails)?rnd=1461679490848"

    DESC_URL = "https://www.walgreens.com/store/store/prodDesc.jsp?id={prod_id}&callFrom=dotcom&instart_disable_injection=true"

    def __init__(self, sort_mode=None, *args, **kwargs):
        if sort_mode:
            if sort_mode.lower() not in self.SORT_MODES:
                self.log('"%s" not in SORT_MODES')
            else:
                self.SORTING = self.SORT_MODES[sort_mode.lower()]

        self.br = BuyerReviewsBazaarApi(called_class=self)

        super(WalGreensProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            url_formatter=FormatterWithDefaults(
                page=self.page,
                sort_mode=self.SORTING or self.SORT_MODES['relevance'],),
            *args,
            **kwargs)

        self.total_matches = None

    def start_requests(self):
        for request in super(WalGreensProductsSpider, self).start_requests():
            if not self.product_url:
                payload = {
                    'p': 1,
                    's': "24",
                    'sort': "relevance",
                    'view': "allView",
                    'geoTargetEnabled': "false",
                    'q': request.meta['search_term'],
                    'abtest': ["tier2","showNewCategories"],
                    'requestType': 'search',
                    'deviceType': 'desktop',
                }
                meta = request.meta
                meta['payload'] = payload

                request = Request(
                    url=self.SEARCH_URL,
                    method='POST',
                    headers={'Content-Type': 'application/json'},
                    body=json.dumps(payload),
                    meta=meta,
                    dont_filter=True
                )
            else:
                request.replace(dont_filter=True)

            yield request

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        prod = response.meta['product']


        no_longer_available = bool(response.xpath(
            '//*[@role="alert"]/span[contains'
            '(text(),"no longer available")]'))

        cond_set_value(prod, 'no_longer_available', no_longer_available)

        prod['url'] = response.url
        prod['locale'] = 'en-US'

        cond_set(
            prod,
            'model',
            response.xpath(
                '//section[@class="panel-body wag-colornone"]/text()'
            ).re('Item Code: (\d+)')
        )

        regex = "[Ii][Dd]=prod(\d+)"
        reseller_id = re.findall(regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(prod, "reseller_id", reseller_id)

        prod_id = re.findall('ID=(.*)-', response.url)
        if prod_id:
            prod_id = prod_id[0]
            review_url = self.REVIEW_API_URL.format(prod_id=prod_id)
            price_variants_url = self.PRICE_VARI_API_URL.format(prod_id=prod_id)

            response.meta['review_url'] = review_url
            yield response.request.replace(
                url=price_variants_url,
                callback=self._parse_data_from_json
            )
        else:
            yield prod

    def _parse_data_from_json(self, response):
        try:
            data = json.loads(response.body)
        except:
            data = {}

        prod = response.meta['product']

        # parse title
        title = data.get('productInfo', {}).get('title')
        cond_set_value(prod, 'title', title)

        # parse sku
        sku = data.get('productInfo', {}).get('skuId') or ''
        sku = re.search('sku(.*)', sku, re.DOTALL)
        if sku:
            sku = sku.group(1)
        cond_set_value(prod, 'sku', sku)

        # parse is_out_of_stock
        stock = data.get('inventory', {}).get('addToCartEnable')
        cond_set_value(prod, 'is_out_of_stock', not stock)

        # parse available_online
        online = data.get('inventory', {}).get('shipAvailable')
        cond_set_value(prod, 'available_online', online)

        # parse image url
        image_url = data.get('productInfo', {}).get('productImageUrl')
        if image_url:
            cond_set_value(prod, 'image_url', urlparse.urljoin("http://", image_url))

        # Parse Price
        if "priceInfo" in data:
            if "messages" in data["priceInfo"]:
                price = None
            elif "salePrice" in data["priceInfo"]:
                price = self.parse_price_single_product(
                    data["priceInfo"], "salePrice")
            elif "regularPrice" in data["priceInfo"]:
                price = self.parse_price_single_product(
                    data["priceInfo"], "regularPrice")
            else:
                price = None

            if price:
                cond_set_value(prod, 'price', Price(price=price[0],
                                                    priceCurrency='USD'))
        # UPC
        upc = data.get('inventory', {}).get('upc')
        cond_set_value(prod, 'upc', upc)

        # In Store Only
        ship_message = data.get('inventory', {}).get('shipAvailableMessage')
        is_in_store_only = (ship_message == "Not sold online")
        cond_set_value(prod, 'is_in_store_only', is_in_store_only)

        # Parse Variants
        colors_variants = data.get('inventory', {}).get(
            'relatedProducts', {}).get('color', [])

        variants = []
        for color in colors_variants:
            vr = {}
            vr['skuID'] = color.get('key', "").replace('sku', '')
            vr['in_stock'] = color.get('isavlbl') == "yes"
            color_name = color.get('value', '').split('-')[0].strip()
            vr['properties'] = {'color': color_name}
            variants.append(vr)

        if variants:
            cond_set_value(prod, 'variants', variants)

        yield response.request.replace(
            url=response.meta['review_url'],
            callback=self._parse_review_api
        )

    def parse_price_single_product(self, data, key):
        price = re.findall(FLOATING_POINT_RGEX, data[key])
        return price

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body)
            self.total_matches = int(data['summary']['productInfoCount'])
        except:
            self.log('Error Parsing total matches: {}'.format(traceback.format_exc()))
        return self.total_matches

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body)
            if 'products' in data:
                items = data['products']
                for item in items:
                    full_link = urlparse.urljoin(
                        self.site,
                        item['productInfo']['productURL'])
                    product = self._get_json_data(item)
                    yield full_link, product
        except:
            self.log('Error Parsing product links: {}'.format(traceback.format_exc()))

    def _scrape_next_results_page_link(self, response):
        meta = response.meta

        current_page = meta.get('current_page', 1)

        if current_page * 24 > self.total_matches:
            return
        meta['current_page'] = current_page + 1
        meta['payload']['p'] = meta['current_page']

        return Request(
                    url=self.SEARCH_URL,
                    method='POST',
                    body=json.dumps(meta['payload']),
                    meta=meta,
                    dont_filter=True
                )

    def _get_json_data(self, item):
        product = SiteProductItem()

        item = item['productInfo']

        if 'salePrice' in item['priceInfo']:
            price = FLOATING_POINT_RGEX.findall(item['priceInfo']['salePrice'])
            if len(price) == 1:
                product['price'] = Price(price=float(price[0].replace(',', '')),
                                         priceCurrency='USD')
            else:
                product['price'] = Price(price=float(price[-1].replace(',', '')),
                                         priceCurrency='USD')
        elif 'regularPrice' in item['priceInfo']:
            price = FLOATING_POINT_RGEX.findall(item['priceInfo']['regularPrice'])
            if len(price) == 1:
                product['price'] = Price(price=float(price[0].replace(',', '')),
                                         priceCurrency='USD')
            else:
                product['price'] = Price(price=float(price[-1].replace(',', '')),
                                         priceCurrency='USD')

        messages = item.get('channelAvailability', [])
        for mes in messages:
            if 'displayText' in mes:
                if 'Not sold online' in mes['displayText']:
                    product['is_in_store_only'] = True
                if 'Out of stock online' in mes['displayText']:
                    product['is_out_of_stock'] = True

        upc = item.get('upc')
        cond_set_value(product, 'upc', upc)

        return product

    def _parse_review_api(self, response):
        product = response.meta['product']
        try:
            raw_json = json.loads(response.body_as_unicode())
        except Exception as e:
            self.log('Invalid reviews: {}'.format(str(e)))
            return product

        buyer_reviews_data = raw_json.get('BatchedResults', {}).get('q0', {})
        response = response.replace(body=json.dumps(buyer_reviews_data))
        buyer_reviews = BuyerReviews(
            **self.br.parse_buyer_reviews_products_json(response))
        product['buyer_reviews'] = buyer_reviews

        # apparently bazaarvoice returns brand info
        brand_data = buyer_reviews_data.get('Results', [])
        if brand_data:
            product['brand'] = brand_data[0].get('Brand', {}).get('Name')

        return product
