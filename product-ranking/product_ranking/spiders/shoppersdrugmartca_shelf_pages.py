# -*- coding: utf-8 -*-

import json
import traceback
from .shoppersdrugmartca import ShoppersdrugmartCaProductsSpider
from scrapy.http import Request
import re

class ShoppersdurgmartCaShelfPagesSpider(ShoppersdrugmartCaProductsSpider):
    name = 'shoppersdrugmartca_shelf_urls_products'
    allowed_domains = ["www1.shoppersdrugmart.ca"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(ShoppersdurgmartCaShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      callback=self._parse_help
                      )

    def _get_form_data(self, response, product_data={}):
        form_data = response.meta.get('form_data', {})
        next_page = product_data.get('SwiftypeResults', {}).get('info', {}).get('page', {}).get('current_page', 0) + 1
        if not form_data:
            it_id = response.xpath('//input[@name="intelliInterface"]/@value').extract()
            cat_id = response.xpath('//input[@class="cat-lan-id"]/@value').extract()

            xid = re.search(r'xpid:"(.*?)"', response.body)
            self.headers['X-NewRelic-ID'] = xid.group(1)

            cat_id = cat_id[0] if cat_id else None
            it_id = it_id[0] if it_id else None

            form_data = {
                'query': '',
                'numRes': '18',
                'facets': 'type,sections',
                'filters': 'type,Product,',
                'getFilters': True,
                'intelliResponseSession': None,
                'intelliInterfaceID': it_id,
                'irResponseId': 0,
                'categoryId': cat_id
            }
        form_data['page'] = next_page
        return form_data

    def _scrape_next_results_page_link(self, response):
        try:
            data = json.loads(response.body)
            current_page = data.get('SwiftypeResults', {}).get('info', {}).get('page', {}).get('current_page')
            if current_page >= self.num_pages:
                return
            return super(ShoppersdurgmartCaShelfPagesSpider, self)._scrape_next_results_page_link(response)
        except:
            self.log('Error Parsing next page link:{}'.format(traceback.format_exc()))
