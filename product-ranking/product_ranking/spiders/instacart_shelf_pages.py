import re
import urlparse
import traceback
import json
from product_ranking.items import SiteProductItem
from .instacart import InstacartProductsSpider
from scrapy import Request

from scrapy.log import ERROR, WARNING


class InstacartShelfPagesSpider(InstacartProductsSpider):
    name = 'instacart_shelf_urls_products'
    allowed_domains = ["instacart.com"]

    SHLEF_URL = "https://www.instacart.com/v3/retailers/3/module_data/" \
                "aisle_{department_id}_{aisle_id}?aisle_id={aisle_id}" \
                "&cache_key=0271eb-617-f-dba" \
                "&department_id={department_id}&source=web" \
                "&tracking.page_view_id=39f2d340-bb2b-4592-ba46-004ccaf5bd84&source=web" \
                "&cache_key=0271eb-617-f-dba&tracking.items_per_row=5&per=30?page={current_page}"

    agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36"
    headers = {'Content-Type': 'application/json', 'User-agent': agent}

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(InstacartShelfPagesSpider, self).__init__(*args, **kwargs)

    def _start_requests(self, response):
        if self.product_url:

            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''

            department_id = re.search('departments/(.*?)/', self.product_url)
            self.department_id = department_id.group(1) if department_id else None

            aisle_id = re.search('aisles/([^?]+)', self.product_url)

            self.aisle_id = aisle_id.group(1) if aisle_id else None

            if department_id and aisle_id:
                yield Request(
                    url=self.SHLEF_URL.format(department_id=self.department_id, aisle_id=self.aisle_id, current_page=self.current_page),
                    meta={
                        "product": prod,
                        'search_term': "",
                        'remaining': self.quantity
                    },
                    headers=self.headers,
                    dont_filter=True,
                )
            else:
                self.log("Failed Parsing ItemID", WARNING)

    def _scrape_total_matches(self, response):
        try:
            total_matches = int(json.loads(response.body).get("module_data").get("pagination").get("total"))
        except ValueError:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
            total_matches = 0

        return total_matches

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body)
            prods = data.get("module_data").get("items", [])
        except ValueError or IndexError:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
            prods = []

        search_term = response.meta['search_term']
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
        if self.current_page >= self.num_pages:
            return

        try:
            data = json.loads(response.body)
            total_page = data.get("module_data").get("pagination").get("next_page")
            if self.current_page >= total_page:
                return None
            self.current_page += 1
            next_link = self.SHLEF_URL.format(department_id=self.department_id, aisle_id=self.aisle_id, current_page=self.current_page)
            return next_link
        except:
            self.log("Failed Parsing Total_Page", WARNING)