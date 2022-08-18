# -*- coding: utf-8 -*-

from .loblawsca import LoblawscaProductsSpider
from scrapy.http import Request
from scrapy.log import INFO, WARNING
import re
import traceback

class LoblawsCAShelfPagesSpider(LoblawscaProductsSpider):
    name = 'loblawsca_shelf_urls_products'
    allowed_domains = ["www.loblaws.ca"]
    CATEGORY_URL = 'https://www.loblaws.ca/plp/{cat_id}?loadMore=true&sort=&filters=&itemsLoadedonPage={page_num}'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        super(LoblawsCAShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        category_id = self.product_url.split('/')[-1]
        if len(category_id) > 1:
            yield Request(url=self.product_url,
                          meta={'search_term': "", 'remaining': self.quantity, 'cat_id': category_id},
                          )
        else:
            self.log("Invalid url!", WARNING)

    def _scrape_total_matches(self, response):
        total_matches = response.xpath('//div[contains(@class, "currently-showing")]/p/text()').extract()
        try:
            total_matches = re.search('(\d+)', total_matches[-1], re.DOTALL).group(1)
            return int(total_matches)
        except:
            self.log('Error while parsing total matches'.format(traceback.format_exc()), INFO)
            return None

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('page_num', 0)
        category_id = response.meta.get('cat_id')
        total_matches = response.meta.get('total_matches')

        if current_page * 60 >= total_matches:
            return
        next_page = current_page + 1
        url = self.CATEGORY_URL.format(page_num=next_page*60, cat_id=category_id)
        return Request(
            url,
            meta={
                'search_term': "",
                'remaining': self.quantity,
                'page_num': next_page,
            }, )