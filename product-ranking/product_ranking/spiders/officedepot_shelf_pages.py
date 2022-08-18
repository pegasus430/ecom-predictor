import re
import urlparse

from scrapy.http import Request

from product_ranking.items import SiteProductItem

is_empty = lambda x: x[0] if x else None

from product_ranking.spiders.officedepot import OfficedepotProductsSpider


class OfficedepotShelfPagesSpider(OfficedepotProductsSpider):
    name = 'officedepot_shelf_urls_products'
    SHELF_URL = "http://www.officedepot.com/mobile/search.do?N={category_id}&recordsPerPageNumber=60&No={offset}"

    def __init__(self, *args, **kwargs):
        self.product_url = kwargs['product_url']
        self.current_page = 1
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', 1))
        super(OfficedepotShelfPagesSpider, self).__init__(*args, **kwargs)

    @staticmethod
    def _get_category_id_from_link(link):
        cid = re.search(r'(?<=/N=.{1}\+)\d+', link)
        return cid.group(0) if cid else None

    def start_requests(self):
        category_id = self._get_category_id_from_link(self.product_url)
        if category_id:
            yield Request(self.SHELF_URL.format(category_id=category_id, offset=0),
                      meta={'remaining': self.quantity,
                            'search_term': '',
                            'category_id': category_id,
                            'offset': 0},
                      dont_filter=True)
        else:
            self.log("Unable to extract category id from given url")

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        total = self._scrape_total_matches(response)
        response.meta['offset'] += 1
        offset = self.productsPerPage * response.meta['offset']
        if offset < total:
            return Request(
                self.url_formatter.format(
                    self.SHELF_URL,
                    category_id=response.meta['category_id'],
                    offset=offset),
                meta=response.meta)
