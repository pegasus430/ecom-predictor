from __future__ import division, absolute_import, unicode_literals

import re
from .gildanonline import GildanOnlineProductsSpider
from scrapy.http import Request
from scrapy.conf import settings

class GildanOnlineShelfPagesSpider(GildanOnlineProductsSpider):
    name = 'gildanonline_shelf_urls_products'
    allowed_domains = ["gildan.com", "goldtoe.com"]

    CATEGORY_URL = 'https://www.gildan.com/rest/model/atg/endeca/assembler/droplet/InvokeAssemblerActor/getContentItem?' \
                   'contentCollection=%2Fcontent%2FWebStoreSS%2FShared%2FListing&' \
                   'N={id}&' \
                   'No={offset}'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(GildanOnlineShelfPagesSpider, self).__init__(
            *args,
            **kwargs)
        settings.overrides['REFERER_ENABLED'] = False

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {
            'remaining': self.quantity,
            'search_term': ''
        }

    def start_requests(self):
        meta = self._setup_meta_compatibility()
        meta['dont_redirect'] = True
        meta['handle_httpstatus_list'] = [302]
        yield Request(url=self.product_url,
                      meta=meta,
                      callback=self._parse_help)

    def _parse_help(self, response):
        if response.status == 302:
            url = response.xpath('//a/@href').extract()[0]
            headers = self.headers.copy()
            headers['Host'] = 'www.goldtoe.com'
            return response.request.replace(headers=headers, url=url)
        id = re.search(r"plp\?N=(.*?)';", response.body)
        if id:
            self.cateory_id = id.group(1)
            url = self.CATEGORY_URL.format(id=self.cateory_id, offset=0)
            return response.request.replace(url=url, callback=self.parse)
        else:
            self.log('Can not get the category id')
            return response.request.replace(headers=self.headers, dont_filter=True)

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        total_matches = meta.get('total_matches', 0)
        results_per_page = meta.get('results_per_page')
        page_num = meta.get('page_num', 1)
        if not results_per_page:
            results_per_page = 12
        if page_num < self.num_pages and total_matches and results_per_page and page_num * results_per_page < total_matches:
            next_link = self.CATEGORY_URL.format(id=self.cateory_id,
                                               offset=page_num * results_per_page)
            meta['page_num'] = page_num + 1
            return Request(
                url=next_link,
                meta=meta,
                dont_filter=True
            )
