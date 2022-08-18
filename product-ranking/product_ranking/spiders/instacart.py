import json
import re
import traceback

from scrapy import Request
from scrapy.conf import settings
from scrapy.log import WARNING

from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider, FormatterWithDefaults,
                                     cond_set_value)
from product_ranking.utils import is_empty
from spiders_shared_code.utils import deep_search


class InstacartProductsSpider(BaseProductsSpider):

    name = 'instacart_products'

    allowed_domains = [
        'instacart.com'
    ]

    HOME_URL = 'https://www.instacart.com/'

    LOG_IN_URL = 'https://www.instacart.com/accounts/login'

    PRODUCT_URL = 'https://www.instacart.com/api/v2/items/{item_id}?source1=store_root&source2=costco&warehouse_id=5' \
                  '&zone_id=27'

    CONTAINER_URL = 'https://www.instacart.com/v3/containers/products/{container_id}?source=web&cache_key={cache_key}'

    SELECT_ZIP_URL = "https://www.instacart.com/v3/bundle?cache_key={cache_key}"

    SEARCH_URL = "https://www.instacart.com/v3/containers/safeway/search_v3/{search_term}" \
                 "?page={current_page}&source=web&cache_key=0271eb-617-f-dba" \
                 "&per=50&tracking.items_per_row=5&tracking.source_url=demo%2Fsearch_v3%2Fmilk" \
                 "&tracking.autocomplete_prefix=null&tracking.autocomplete_selected_position=-1"

    LOGIN_BODY = 'user%5Bemail%5D={email}&user%5Bpassword%5D={password}&authenticity_token={token}'
    LOGIN_EMAIL = 't3187425@mvrht.net'
    LOGIN_PASSWORD = 't3187425@mvrht.net'

    agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36"
    headers = {'Content-Type': 'application/json', 'User-agent': agent}

    handle_httpstatus_list = [422]

    def __init__(self, zip='94117', *args, **kwargs):
        self.zip = zip
        self.cache_key = None
        url_formatter = FormatterWithDefaults(current_page=1)
        super(InstacartProductsSpider, self).__init__(
            url_formatter=url_formatter,
            site_name=self.allowed_domains[0],
            *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        yield Request(
            url=self.HOME_URL,
            dont_filter=True,
            callback=self.start_requests_with_csrf,
        )

    def start_requests_with_csrf(self, response):
        csrf = self.get_csrf(response)
        if csrf:
            yield Request(
                url=self.LOG_IN_URL,
                callback=self.homepage,
                method="POST",
                body=self.LOGIN_BODY.format(
                    email=self.LOGIN_EMAIL,
                    password=self.LOGIN_PASSWORD,
                    token=csrf
                ),
                dont_filter=True,
                headers={
                    'X-CSRF-Token': csrf,
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Origin': 'https://www.instacart.com',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.84 Safari/537.36'
                }
            )
        else:
            self.log("Failed Parsing CSRF", WARNING)

    def homepage(self, response):
        yield Request(
            self.HOME_URL,
            callback=self._set_zip,
            headers=self.headers
        )

    def _set_zip(self, response):
        self.cache_key = 'ce166f-394-t-0b5'
        url = self.SELECT_ZIP_URL.format(cache_key=self.cache_key)
        token = self.get_csrf(response)
        self.headers['x-csrf-token'] = token

        payload = {
            'active_service_type': 'delivery',
            'current_address_id': None,
            'current_zip_code': self.zip
        }

        yield Request(
            url=url,
            callback=self._start_requests,
            method="PUT",
            body=json.dumps(payload),
            dont_filter=True,
            headers=self.headers
        )

    def _start_requests(self, response):
        for request in super(InstacartProductsSpider, self).start_requests():
            if self.product_url:
                item_id = re.search('items/(item_)?(\d+)', self.product_url)
                item_id = item_id.group(2) if item_id else None
                container_id = re.search('products/(\d+)', self.product_url)
                container_id = container_id.group(1) if container_id else None
                if item_id:
                    url = self.PRODUCT_URL.format(item_id=item_id)
                    request = request.replace(url=url)
                elif container_id:
                    url = self.CONTAINER_URL.format(container_id=container_id, cache_key=self.cache_key)
                    request = request.replace(url=url, callback=self._parse_container)
            request = request.replace(dont_filter=True, headers=self.headers)
            yield request

    def _parse_container(self, response):
        meta = response.meta.copy()
        product = response.meta.get('product', SiteProductItem())
        container_data = None

        try:
            container_data = json.loads(response.body)
        except:
            self.log('Error Parsing Container Json: {}'.format(traceback.format_exc()))

        if container_data:
            container_data = container_data.get('container', {}).get('modules', [])
            for module in container_data:
                if module.get('types') and module.get('types')[0] == 'item/product_detail':
                    if module.get('data', {}).get('retailer_actions'):
                        path = module.get('data', {}).get('retailer_actions')[0].get('action', {})\
                            .get('data', {}).get('display_path')
                        item_id = re.search(r'items/(\d+)', path)
                        if item_id:
                            url = self.PRODUCT_URL.format(item_id=item_id.group(1))
                            return Request(
                                url,
                                self._parse_single_product,
                                meta=meta,
                                headers=self.headers
                            )
                    else:
                        product['title'] = module.get('data', {}).get('product', {}).get('name')
                        if module.get('data', {}).get('product', {}).get('image_list'):
                            product['image_url'] = module['data']['product']['image_list'][0]['url']
                        product['no_longer_available'] = True
                        product['is_out_of_stock'] = True

        return product

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        product['locale'] = "en_EN"

        try:
            products = json.loads(response.body)
            product_data = products.get('data')

        except:
            self.log('JSON not found or invalid JSON: {}'.format(traceback.format_exc()))
            product['not_found'] = True
            return product

        title = self._parse_title(product_data)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(product_data)
        cond_set_value(product, 'brand', brand)

        cond_set_value(product, 'is_out_of_stock', False)

        price = self._parse_price(product_data)
        cond_set_value(product, 'price', price)

        image_url = self._parse_image_url(product_data)
        cond_set_value(product, 'image_url', image_url)

        description = self._parse_description(product_data)
        cond_set_value(product, 'description', description)

        sku = self._parse_sku(product_data)
        cond_set_value(product, 'sku', sku)

        return product

    def _parse_title(self, product_data):
        return product_data.get('display_name')

    def _parse_brand(self, product_data):
        return product_data.get('brand_name')

    def _parse_price(self, product_data):
        price = product_data.get('price')

        if price:
            price = Price('USD', float(price))
        else:
            price = None

        return price

    def _parse_image_url(self, product_data):
        return product_data.get('large_image_url')

    def _parse_description(self, product_data):
        return product_data.get('disclaimer')

    def _parse_sku(self, product_data):
        return product_data.get('id')

    def _scrape_total_matches(self, response):
        try:
            total_matches = int(deep_search('total', json.loads(response.body))[0])
        except Exception as e:
            self.log('Invalid JSON: {}'.format(traceback.format_exc(e)), WARNING)
            total_matches = None

        return total_matches

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body)
            prods = deep_search('items', data)[0]
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
            prods = []

        search_term = response.meta.get('search_term')
        for prod in prods:
            item_id = prod.get("legacy_id")
            if item_id:
                prod_item = SiteProductItem()
                req = Request(
                    url=self.PRODUCT_URL.format(item_id=item_id),
                    meta={
                        "product": prod_item,
                        'search_term': search_term,
                        'remaining': self.quantity
                    },
                    headers=self.headers,
                    dont_filter=True,
                    callback=self._parse_single_product
                )
                yield req, prod_item
            else:
                self.log("Failed Parsing ItemID", WARNING)

    def _scrape_next_results_page_link(self, response):
        search_term = response.meta.get('search_term')
        current_page = response.meta.get('current_page', 1)
        try:
            if current_page >= self._scrape_total_matches(response):
                return None

            current_page += 1

            return Request(
                url=self.SEARCH_URL.format(search_term=search_term, current_page=current_page),
                dont_filter=True,
                meta={'search_term': search_term, 'remaining': self.quantity, 'current_page': current_page},
                headers=self.headers,
            )
        except Exception as e:
            self.log('Next Page Error: {}'.format(traceback.format_exc(e)), WARNING)

    def get_csrf(self, response):
        return is_empty(response.xpath(
                        "//meta[@name='csrf-token']/@content").extract())
