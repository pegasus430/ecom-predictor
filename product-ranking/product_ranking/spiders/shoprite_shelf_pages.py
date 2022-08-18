import json
import re
from product_ranking.utils import catch_json_exceptions
from scrapy.http import Request
from .shoprite import ShopriteProductsSpider


class ShopriteShelfPagesSpider(ShopriteProductsSpider):
    name = 'shoprite_shelf_urls_products'
    PRODUCTS_URL = "https://shop.shoprite.com/api/product/v7/products/category/" \
                   "{category_id}/store/{store}?sort=Brand&skip={skip}&take=20&userId={user_id}"

    CATEGORIES_URL = "https://shop.shoprite.com/api/product/v7/categories/store/{store}"

    def __init__(self, *args, **kwargs):
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(ShopriteShelfPagesSpider, self).__init__(*args, **kwargs)
        self.store = self._parse_store(self.product_url)
        self.categories = []
        self._categories = self._parse_categories_from_url(self.product_url)
        self.current_page = 1

    def start_requests(self):
        if self.product_url:
            yield Request(self.product_url,
                          self._parse_helper,
                          meta={'search_term': '',
                                'remaining': self.quantity})

    def _parse_shelf_path(self):
        return self.categories

    def _parse_shelf_name(self):
        return self.categories[-1]

    def _parse_configuration(self, response):
        configuration = self._parse_info(response)
        return configuration

    @staticmethod
    def _parse_request_headers(response, token):
        return {
            'Authorization': token,
            'Referer': response.url,
            'Accept': 'application/vnd.mywebgrocer.wakefern-product-list+json'

        }

    def _parse_helper(self, response):
        meta = response.meta
        if not meta.get('token'):
            configuration = self._parse_configuration(response)
            meta['token'] = self._parse_token(configuration)
            meta['user_id'] = self._parse_user_id(configuration)
            meta['headers'] = self._parse_request_headers(response, meta['token'])
            return Request(
                self.CATEGORIES_URL.format(store=self.store),
                headers={
                    'Accept': 'application/vnd.mywebgrocer.category-tree+json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Authorization': meta['token']
                },
                meta=meta,
                callback=self._get_categories_names
            )
        return Request(
            self.PRODUCTS_URL.format(
                user_id=meta['user_id'],
                store=self.store,
                skip=response.meta.get('skip', 0),
                category_id=self._categories[-1]
            ),
            headers=meta['headers'],
            meta=meta,
            dont_filter=True
        )

    @catch_json_exceptions
    def _get_categoties_json(self, response):
        return json.loads(response.body)

    def _search_category(self, target_id, categories_data):
        found = []

        if isinstance(categories_data, dict):
            if target_id == categories_data.get('Id'):
                found.append(categories_data)

            elif len(categories_data.get('Subcategories', [])) > 0:
                for data in categories_data.get('Subcategories'):
                    result = self._search_category(target_id, data)
                    found.extend(result)

        elif isinstance(categories_data, list):
            for data in categories_data:
                result = self._search_category(target_id, data)
                found.extend(result)

        return found

    def _get_categories_names(self, response):
        categories_data = self._get_categoties_json(response)
        for category_id in self._categories:
            try:
                category_data = self._search_category(int(category_id), categories_data)
                if category_data:
                    self.categories.append(category_data[0].get('Name'))
            except ValueError:
                self.log('Wrong `categpry_id`: {}'.format(category_id))
        return Request(
            self.PRODUCTS_URL.format(
                user_id=response.meta['user_id'],
                store=self.store,
                skip=response.meta.get('skip', 0),
                category_id=self._categories[-1]
            ),
            headers=self._parse_request_headers(response, response.meta.get('token')),
            meta=response.meta,
            dont_filter=True
        )

    @staticmethod
    def _parse_categories_from_url(url):
        pattern = re.compile(r'/category/(.+?)/')
        found = pattern.findall(url)
        return found[0].split(',') if found else None

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        info = json.loads(response.body)
        page = info.get('PageLinks')[-1]
        skip = info.get('Skip') + 20
        if page.get('Rel') == 'next':
            response.meta['skip'] = skip
            return self._parse_helper(response)
