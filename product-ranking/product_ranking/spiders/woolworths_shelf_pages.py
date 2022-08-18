from __future__ import absolute_import, division, unicode_literals

import json
import re
import traceback
import urllib
import urlparse

from scrapy.http import Request
from scrapy.log import ERROR

from .woolworths import WoolworthsProductsSpider


class WoolworthsShelfPagesSpider(WoolworthsProductsSpider):
    name = 'woolworths_shelf_urls_products'
    allowed_domains = ["www.woolworths.com.au"]

    SHELF_URL = 'https://www.woolworths.com.au/apis/ui/browse/category' \
                '?categoryId={category_id}&formatObject={{"name":"{description}"}}&isBundle=false&isMobile=true' \
                '&isSpecial=false&pageNumber={page_number}&pageSize=24&sortType=TraderRelevance&url={path}'

    def __init__(self, *args, **kwargs):
        if kwargs.get('quantity'):
            kwargs.pop('quantity')
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(WoolworthsShelfPagesSpider, self).__init__(
            *args,
            **kwargs)
        self.total_matches_field_name = "TotalRecordCount"
        self.product_links_field_name = "Bundles"
        self.shelf_format = {}
        self.shelf_url = None

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}

    def start_requests(self):
        yield Request(url=self.product_url.replace("\'", ""),
                      meta=self._setup_meta_compatibility(),
                      callback=self._parse_helper)

    def _parse_helper(self, response):
        parsed_url = urlparse.urlparse(response.url)
        self.path = parsed_url.path
        self.url_friendly_name = self.path.split('/')[-1].lower().strip()
        try:
            json_data = json.loads(
                response.xpath('//script[contains(text(), "window.wowBootstrap = ")]/text()').re(
                    re.compile(r'window\.wowBootstrap\s*=\s*({.+?});')
                )[0]
            )
        except:
            self.log('Can not extract json data: {}'.format(traceback.format_exc()), ERROR)
        else:
            categories = json_data['ListAllPiesCategoriesWithSpecialsRequest']['Categories']
            for category in categories:
                self.tree_traversal(category['Children'])
                if self.shelf_url:
                    yield Request(self.shelf_url, meta=response.meta)
                    return

    def _scrape_next_results_page_link(self, response):
        if self.current_page < self.num_pages:
            self.current_page += 1
            self.shelf_format['page_number'] = self.current_page
            return self.SHELF_URL.format(**self.shelf_format)


    def tree_traversal(self, children):
        for child in children:
            if self.url_friendly_name == child.get('UrlFriendlyName', '').lower().strip():
                self.shelf_format = {'path': self.path,
                                     'category_id': child['NodeId'],
                                     'description': urllib.quote_plus(child['Description'].encode('utf-8')),
                                     'page_number': self.current_page
                                     }
                self.shelf_url = self.SHELF_URL.format(**self.shelf_format)
                return
            else:
                self.tree_traversal(child['Children'])
