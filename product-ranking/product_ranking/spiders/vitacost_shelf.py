# -*- coding: utf-8 -*-

import re
import json
import traceback

from .vitacost import VitacostProductsSpider
from scrapy.http import Request
from scrapy.log import WARNING


class VitacostShelfPagesSpider(VitacostProductsSpider):
    name = 'vitacost_shelf_urls_products'
    allowed_domains = ["www.vitacost.com"]

    ASPX_SHELF_URL = "https://www.vitacost.com/productResults.aspx?{shelf_param}" \
                     "&scrolling=true&No={offset}"

    SHELF_URL = "https://www.vitacost.com/productResults.aspx?N={model}" \
                "&seoText={shelf_param}&scrolling=true&No={offset}"

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(VitacostShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        meta = {'search_term': '',
                'remaining': self.quantity,
                'current_page': 1,
                'results_per_page': 20
                }
        url = None
        if 'aspx' in self.product_url:
            shelf_param = re.search('aspx\?(.*)', self.product_url)
            if shelf_param:
                shelf_param = shelf_param.group(1)
                url = self.ASPX_SHELF_URL.format(shelf_param=shelf_param, offset=0)
                meta['shelf_param'] = shelf_param
                req = Request(
                    url=url,
                    meta=meta
                )
        else:
            shelf_param = self.product_url.split('/')[-1]
            if shelf_param:
                meta['shelf_param'] = shelf_param
                url = self.product_url
                req = Request(
                    url=url,
                    callback=self._start_requests,
                    meta=meta
                )
        if url:
            yield req
        else:
            self.log("Found no shelf param in {url}".format(url=self.product_url), WARNING)

    def _start_requests(self, response):
        meta = response.meta.copy()
        sp = meta.get('shelf_param')

        try:
            content = json.loads(re.search('bumblebee.ini\((.*?)\);', response.body).group(1))
            model = content.get('data', {}).get('n')
            meta['model'] = model
            url = self.SHELF_URL.format(model=model, shelf_param=sp, offset=0)
            return Request(
                url=url,
                meta=meta
            )
        except:
            self.log('Error while parsing the shelf url'.format(traceback.format_exc()))

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()

        current_page = meta.get('current_page')
        results_per_page = meta.get('results_per_page')
        sp = meta.get('shelf_param')
        model = meta.get('model')

        total = self._scrape_total_matches(response)
        offset = current_page * results_per_page
        if total and offset >= total:
            return
        current_page += 1

        meta['current_page'] = current_page
        if 'aspx' in self.product_url:
            next_page_link = self.ASPX_SHELF_URL.format(shelf_param=sp, offset=offset)
        else:
            next_page_link = self.SHELF_URL.format(model=model, shelf_param=sp, offset=offset)
        return Request(
            url=next_page_link,
            meta=meta
        )