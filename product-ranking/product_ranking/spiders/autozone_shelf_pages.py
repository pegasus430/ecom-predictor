# -*- coding: utf-8 -*-

from .autozone import AutozoneProductsSpider
from scrapy.http import Request
import re
import traceback
from urlparse import urljoin
from product_ranking.utils import is_empty

class AutozoneShelfPagesSpider(AutozoneProductsSpider):
    name = 'autozone_shelf_urls_products'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(AutozoneShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity}
                      )

    def _scrape_total_matches(self, response):
        data = re.search(r'resultsSize = \'(\d{1,3}[,\d{3}]*)\'', response.body)
        try:
            return int(data.group(1).replace(',', ''))
        except:
            self.log('Error Parsing the Total matches of shelf: {}'.format(traceback.format_exc()))

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return None
        current_page += 1
        response.meta['current_page'] = current_page
        next_link = is_empty(response.xpath('//a[@id="next"]/@href').extract())
        if next_link:
            return Request(
                urljoin(response.url, next_link),
                meta=response.meta
            )