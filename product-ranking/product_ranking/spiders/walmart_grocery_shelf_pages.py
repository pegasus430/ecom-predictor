import re
import json
import traceback

from scrapy.log import ERROR
from scrapy.http import Request

from product_ranking.spiders.walmart_grocery import WalmartGroceryProductSpider


class WalmartGroceryShelfPagesSpider(WalmartGroceryProductSpider):
    name = 'walmart_grocery_shelf_urls_products'
    allowed_domains = ['grocery.walmart.com']

    SHELF_URL = 'https://grocery.walmart.com/v3/api/products' \
                '?strategy=aisle&taxonomyNodeId={aisle_id}&storeId={store_id}&count={results_per_page}' \
                '&page={page_num}&offset={offset}'

    aisle_id = None

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(WalmartGroceryShelfPagesSpider, self).__init__(*args,	**kwargs)

    @staticmethod
    def _extract_aisle(product_url):
        aisle_id = re.search(r'aisle=(.*)', product_url)
        if aisle_id:
            return aisle_id.group(1)

    def post_start_request(self, response):
        self.parse_store_id(response)
        self.aisle_id = self._extract_aisle(self.product_url)

        if self.aisle_id:
            yield Request(
                url=self.SHELF_URL.format(
                    aisle_id=self.aisle_id,
                    store_id=self.store_id,
                    results_per_page=self.results_per_page,
                    page_num=self.current_page,
                    offset=0,
                ),
                meta={
                    'remaining': self.quantity,
                    'search_term': '',
                    'offset': 0,
                }
            )

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return None
        self.current_page += 1
        try:
            data = json.loads(response.body, encoding='utf-8')
            offset = response.meta['offset'] + self.results_per_page
            # totalCount is int type
            if offset < data.get('totalCount'):
                return Request(
                    url=self.url_formatter.format(
                        self.SHELF_URL,
                        aisle_id=self.aisle_id,
                        store_id=self.store_id,
                        results_per_page=self.results_per_page,
                        page_num=self.current_page,
                        offset=offset,
                    ),
                    meta={
                        'remaining': self.quantity,
                        'search_term': '',
                        'offset': offset,
                    }
                )
        except:
            self.log(
                'Error while parsing next_results_page_link {}'.format(traceback.format_exc()),
                level=ERROR,
            )