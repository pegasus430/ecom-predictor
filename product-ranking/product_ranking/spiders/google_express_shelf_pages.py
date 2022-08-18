# -*- coding: utf-8 -*-

from .google_express import GoogleExpressProductsSpider
from scrapy.http import Request
import re
import time
import urllib

class GoogleExpressShelfPagesSpider(GoogleExpressProductsSpider):
    name = 'google_express_shelf_urls_products'
    allowed_domains = ["google.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(GoogleExpressShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        cat_id = re.search('cat=(.*)', self.product_url, re.DOTALL)
        if cat_id:
            cat_id = cat_id.group(1)

        formdata = {
            'f.req': '[[[142508757,[{'
                     + '"142508757":[null,"%s",null,null,1,"ALEfSmfOAWEPJTYtm9ozpf7Y'
                       '_WR7GzLZRtcm0Q8X9bk60hZASNtvPtO4Kgj9U6AYjkDVBPL-mBoSo4pwHGqalhkH1Svs'
                       '-bjrHTrzZrK-x8BmtnmUzq5R-vZPVuwpzYyI-yBa8_gmJsngkpyDSyboBujQD'
                       '_REddR4udG7IGk0yVYW2ZgoEVnsoQR70iLirhpp7BkHsgh8CVS8uejVdjAogAVo6ozWip8zBrsCyNI1A3fg'
                       '0JsXCOUon9Q3GRlbYDGh3ZeprpjnAbzc","/search?cat=%s"]'
                     + '}],null,null,0]]]'
        }

        formdata_model = formdata.copy()
        formdata_model['f.req'] = formdata_model['f.req'] % ('', cat_id)

        req_id = int(time.time())
        req_id = str(req_id)[3:]

        request = Request(
            url=self.SEARCH_URL.format(req_id=req_id),
            method='POST',
            body=urllib.urlencode(formdata_model),
            meta={'req_id': req_id, 'cat_id': cat_id, 'formdata': formdata, 'remaining': self.quantity, 'search_term': ""},
            dont_filter=True,
            headers=self.HEADERS
        )
        yield request

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return
        return super(GoogleExpressShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)