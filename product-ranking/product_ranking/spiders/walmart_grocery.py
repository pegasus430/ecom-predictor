import json
import re
import traceback
import urllib

from scrapy.conf import settings
from scrapy.http import Request
from scrapy.log import ERROR, WARNING

from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value


class WalmartGroceryProductSpider(BaseProductsSpider):
    name = 'walmart_grocery_products'
    allowed_domains = ['grocery.walmart.com']

    CURRENCY = 'USD'

    SEARCH_URL = 'https://grocery.walmart.com/v3/api/products?strategy=search&itemFields=all&itemFields=store' \
                 '&storeId={store_id}&query={search_term}&count={results_per_page}&offset={offset}'

    STORE_URL = 'https://grocery.walmart.com/v3/api/serviceAvailability?postalCode={zip_code}'

    PRODUCT_URL = 'https://grocery.walmart.com/v3/api/products/{sku}?itemFields=all&storeId={store_id}'

    ORIGINAL_PRODUCT_URL = 'https://grocery.walmart.com/product/{sku}'

    results_per_page = 60
    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36"

    handle_httpstatus_list = [404]

    def __init__(self, *args, **kwargs):
        super(WalmartGroceryProductSpider, self).__init__(*args, **kwargs)
        self.zip_code = kwargs.pop('zip_code', '72758')
        self.store_id = kwargs.pop('store', '5260')

        DEFAULT_REQUEST_HEADERS = settings.get('DEFAULT_REQUEST_HEADERS')
        DEFAULT_REQUEST_HEADERS['X-Forwarded-For'] = '127.0.0.1'

        retry_codes = settings.get('RETRY_HTTP_CODES')
        if 404 in retry_codes:
            retry_codes.remove(404)

        settings.overrides['USE_PROXIES'] = True

    def _parse_single_product(self, response):
        product = response.meta['product']
        try:
            raw_product_data = json.loads(response.body, encoding='utf-8')
            return self.populate_product(product, raw_product_data)
        except:
            self.log(
                'Error while parsing single product {}'.format(traceback.format_exc()),
                level=ERROR,
            )

    def parse_product(self, response):
        return response.meta['product']

    def populate_product(self, product, raw_data):
        if raw_data.get('statusCode') == 404:
            self.log('Product not found')
            cond_set_value(product, 'not_found', True)
            return product

        # Parse title
        title = raw_data.get('basic', {}).get('name', None)
        cond_set_value(product, 'title', title)

        # Parse brand
        brand = raw_data.get('detailed', {}).get('brand', None)
        cond_set_value(product, 'brand', brand)

        # Parse department
        department = raw_data.get('basic', {}).get('primaryDepartment', {}).get('name', None)
        cond_set_value(product, 'department', department)

        # Parse description
        description = raw_data.get('detailed', {}).get('description', None)
        cond_set_value(product, 'description', description)

        # Parse total_matches
        total_matches = raw_data.get('totalCount')
        cond_set_value(product, 'total_matches', total_matches)

        # Parse price
        price = raw_data.get('store', {}).get('price', {}).get('list', None)
        if price:
            price = Price(
                priceCurrency=self.CURRENCY,
                price=price
            )
        cond_set_value(product, 'price', price)

        # Parse reseller_id
        reseller_id = raw_data.get('USItemId', None)
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse sku
        sku = raw_data.get('productId', None)
        cond_set_value(product, 'sku', sku)

        # Parse upc
        upc = raw_data.get('upcs', None)
        if upc:
            upc = upc[0]
        cond_set_value(product, 'upc', upc)

        # Parse image url
        image_url = raw_data.get('basic', {}).get('image', {}).get('large', None) # Returns full url
        cond_set_value(product, 'image_url', image_url)

        # Parse stock status
        out_of_stock = bool(raw_data.get('basic', {}).get('isOutOfStock', None))
        cond_set_value(product, 'is_out_of_stock', out_of_stock)

        # Set product url
        if not product.get('url', None) and reseller_id:
            product_url = self.ORIGINAL_PRODUCT_URL.format(sku=reseller_id)
            cond_set_value(product, 'url', product_url)

        cond_set_value(product, 'store', self.store_id)
        cond_set_value(product, 'zip_code', self.zip_code)

        return product

    def start_requests(self):
        yield Request(
            url=self.url_formatter.format(
                self.STORE_URL,
                zip_code=self.zip_code,
            ),
            callback=self.post_start_request,
        )

    def post_start_request(self, response):
        self.parse_store_id(response)

        for st in self.searchterms:
            yield Request(
                url=self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote(st.encode('utf-8')),
                    store_id=self.store_id,
                    results_per_page=self.results_per_page,
                    offset=0,
                ),
                meta={
                    'search_term': st,
                    'remaining': self.quantity,
                    'offset': 0,
                }
            )

        if self.product_url:
            sku = self._extract_sku(self.product_url)

            if sku:
                prod = SiteProductItem()
                prod['is_single_result'] = True
                prod['sku'] = sku
                prod['url'] = self.product_url
                prod['search_term'] = ''
                yield Request(
                    url=self.PRODUCT_URL.format(
                        sku=sku,
                        store_id=self.store_id
                    ),
                    callback=self._parse_single_product,
                    meta={
                        'product': prod
                    }
                )
            else:
                self.log(
                    'Product url doesn\'t contain SKU',
                    level=ERROR
                )

    @staticmethod
    def _extract_sku(product_url):
        sku = re.search(r'product\/(\d+)', product_url)
        if not sku:
            sku = re.search(r'skuId=(\d+)', product_url)
        if sku:
            return sku.group(1)

    def parse_store_id(self, response):
        try:
            data = json.loads(response.body, encoding='utf-8')
            if data.get('storeId'):
                self.store_id = data.get('storeId')
        except:
            self.log(
                'Error while parsing store_id {}. Using default value.'.format(traceback.format_exc()),
                level=WARNING,
            )

    def _scrape_next_results_page_link(self, response):
        try:
            data = json.loads(response.body, encoding='utf-8')
            offset = response.meta['offset'] + self.results_per_page
            # totalCount is int type
            if offset < data.get('totalCount'):
                st = response.meta['search_term']
                return Request(
                    url=self.url_formatter.format(
                        self.SEARCH_URL,
                        search_term=urllib.quote(st.encode('utf-8')),
                        store_id=self.store_id,
                        results_per_page=self.results_per_page,
                        offset=offset,
                    ),
                    meta={
                        'search_term': st,
                        'remaining': self.quantity,
                        'offset': offset,
                    }
                )
        except:
            self.log(
                'Error while parsing next_results_page_link {}'.format(traceback.format_exc()),
                level=ERROR,
            )

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body, encoding='utf-8')
            # totalCount is int type
            total_matches = data.get('totalCount')
            return total_matches
        except:
            self.log(
                'Error while parsing total_matches {}'.format(traceback.format_exc()),
                level=ERROR,
            )

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body, encoding='utf-8')
            for raw_product_data in data.get('products', []):
                item = self.populate_product(SiteProductItem(), raw_product_data)
                yield None, item
        except:
            self.log(
                'Error while parsing product links {}'.format(traceback.format_exc()),
                level=ERROR,
            )
