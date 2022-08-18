from __future__ import division, absolute_import, unicode_literals

import re
import traceback
import json

from product_ranking.spiders.asda import AsdaProductsSpider
from scrapy.http import Request


class AsdaShelfPagesSpider(AsdaProductsSpider):
    name = 'asda_shelf_urls_products'
    allowed_domains = ["asda.com"]

    prods_per_page = 60

    CATEGORY_URL = "https://groceries.asda.com/api/items/viewitemlist?catid={catid}&deptid={deptid}" \
                   "&aisleid={aisleid}&showfacets=1&pagesize={prods_per_page}&pagenum={pagenum}" \
                   "&contentids=New_IM_ShelfPage_FirstRow_1%2CNew_IM_ShelfPage_LastRow_1%2CNew_IM_SEO_ListingPage_Bottom_promo" \
                   "%2CNew_IM_Second_Navi_Shelf&storeid=4565&cacheable=true&shipDate=currentDate" \
                   "&sortby=relevance+desc&facets=shelf%3A0000%3A{catid}&requestorigin=gi"

    CATEGORIES_URL = "https://groceries.asda.com/api/categories/viewmenu?" \
                     "cacheable=true&storeid=4565&requestorigin=gi"

    use_proxies = False

    HEADERS = {
        'Accept-Language': 'en-US,en;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_2) ' \
                      'AppleWebKit/537.36 (KHTML, like Gecko)' \
                      'Chrome/55.0.2883.95 Safari/537.36',
        'x-forwarded-for': '127.0.0.1'
    }

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))
        self.search_term = ''

        self.categories = []
        self.category_id = 0
        self.department_id = 0
        self.aisle_id = 0

        super(AsdaShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        try:
            self.search_term = re.search('shelf/(.*)', self.product_url).group(1).split('/')[1]
        except Exception as e:
            self.log('Error while parsing search_term {}'.format(traceback.format_exc(e)))

        return {'remaining': self.quantity, 'search_term': self.search_term}.copy()

    def start_requests(self):
        yield Request(
            self.CATEGORIES_URL,
            headers=self.HEADERS,
            callback=self._start_requests
        )

    def _start_requests(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            self.categories = data.get('categories')
        except Exception as e:
            self.log('Error while parsing categories {}'.format(traceback.format_exc(e)))

        category, dept, aisle, shelf = self._get_path()

        if dept and aisle:
            self.department_id = dept
            self.aisle_id = aisle
            self.category_id = shelf

            yield Request(
                self.CATEGORY_URL.format(
                    pagenum=self.current_page,
                    prods_per_page=self.prods_per_page,
                    search_term=self.search_term,
                    catid=self.category_id,
                    deptid=self.department_id,
                    aisleid=self.aisle_id
                ),
                meta=self._setup_meta_compatibility()
            )

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return

        try:
            data = json.loads(response.body_as_unicode())
            max_page = int(data['maxPages'])
            if self.current_page >= max_page:
                return

            self.current_page += 1

            return Request(
                self.CATEGORY_URL.format(
                    pagenum=self.current_page,
                    prods_per_page=self.prods_per_page,
                    search_term=self.search_term,
                    catid=self.category_id,
                    deptid=self.department_id,
                    aisleid=self.aisle_id
                ),
                meta=self._setup_meta_compatibility(),
                headers=self.HEADERS,
            )
        except Exception as e:
            self.log('Page Count Error {}'.format(traceback.format_exc(e)))

    def _get_path(self):
        try:
            wrap = re.findall('(?<=/)\d+', self.product_url)[0]

            for category in self.categories:
                depts = category.get('categories', [])
                for dept in depts:
                    aisles = dept.get('categories', [])
                    for aisle in aisles:
                        shelves = aisle.get('categories', [])
                        for shelf in shelves:

                            if wrap == shelf.get('dimensionid'):
                                return category.get('id'), dept.get('id'), aisle.get('id'), shelf.get('id')
        except Exception as e:
            self.log('Error while parsing categories {}'.format(traceback.format_exc(e)))

        return None, None, None, None
