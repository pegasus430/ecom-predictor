# -*- coding: utf-8 -*-

import json
import urllib
import urlparse

from scrapy.log import WARNING
from scrapy.http import Request
from scrapy.conf import settings

from product_ranking.items import SiteProductItem
from product_ranking.spiders.amazoncouk import AmazonProductsSpider as _AmazonProductsSpider


class AmazonProductsSpider(_AmazonProductsSpider):
    name = 'amazoncouk_mobile_products'
    CID = '08e6b9c8bdfc91895ce634a035f3d00febd36433' # TODO: find how CID generates, try another device and compare
    APPENDIX = '&dataVersion=v0.2&format=json&cid={cid}'.format(cid=CID)
    SEARCH_URL = 'https://www.amazon.co.uk/s/ref=nb_sb_ss_sh_1_0' \
                 '?k={search_term}' \
                 '&rh=i:aps,k:{search_term}'
    SORT_MODES = {} # TODO: Add sort modes support

    MODEL = 'K920'
    OS = 'Android'
    OS_VERSION = '6.0.1'
    MOBILE_USER_AGENT = 'Amazon.com/10.8.0.100 ({os}/{os_version}/{model})'.format(
        os=OS,
        os_version=OS_VERSION,
        model=MODEL
    )

    def __init__(self, sort_mode='', *args, **kwargs):
        if sort_mode not in self.SORT_MODES:
            self.log('"%s" not in SORT_MODES')
        super(AmazonProductsSpider, self).__init__(*args, **kwargs)

        settings.overrides['USE_PROXIES'] = True

    def start_requests(self):
        # TODO: split realization of the method in base class for better override
        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(
                url=self.product_url,
                callback=self._parse_single_product,
                meta={'product': prod}
            )
        if self.searchterms:
            for st in self.searchterms:
                yield Request(
                    self.url_formatter.format(
                        self.SEARCH_URL + self.APPENDIX,
                        search_term=urllib.quote_plus(st.encode('utf-8')).replace(' ', '+'),
                    ),
                    meta={
                        'search_term': st,
                        'remaining': self.quantity
                    },
                    headers={
                        'Referer': None
                    },
                )

    # TODO: refactor method in BaseProductsSpider for don't do that crazy tricks
    def _get_next_products_page(self, response, prods_found):
        return super(AmazonProductsSpider, self)._get_next_products_page(response, prods_found)

    def _scrape_total_matches(self, response):
        try:
            total = int(self._get_metadata(response).get('totalResults', 0))
        except (ValueError, TypeError):
            total = 0
        return total

    def _scrape_product_links(self, response):
        links = self._parse_links_in_items(
            items=self._parse_items_in_section(
                sections=self._get_sections(
                    response=response
                )
            )
        )
        for link, is_prime, is_prime_pantry, is_sponsored in links:
            link = urlparse.urljoin(response.url, link)
            # TODO: Add support of prime-pantry? and sponsored
            prod = SiteProductItem(
                prime='Prime' if is_prime else None
            )
            yield Request(
                link,
                callback=self.parse_product,
                meta={
                    'product': prod
                }
            ), prod

    def _scrape_next_results_page_link(self, response):
        pages = None
        if self._get_pagination(response):
            pages = self._get_pagination(response).get('pages', None)
        if pages and isinstance(pages, list):
            for page in pages:
                if page.get('type', None) == u'next':
                    next = page.get('link', {}).get('url', None)
                    if next:
                        return urlparse.urljoin(response.url, next + self.APPENDIX)
        return None

    def _get_metadata(self, response):
        try:
            return json.loads(response.body, encoding='utf-8').get('resultsMetadata', {})
        except ValueError:
            self.log('Can\'t decode JSON response for search term "{}"'.format(
                response.meta.get('search_term')
            ), level=WARNING)

    def _get_sections(self, response):
        try:
            return json.loads(response.body, encoding='utf-8').get('results', {}).get('sections', [])
        except ValueError:
            self.log('Can\'t decode JSON response for search term "{}"'.format(
                response.meta.get('search_term')
            ), level=WARNING)

    def _get_pagination(self, response):
        try:
            return json.loads(response.body, encoding='utf-8').get('pagination', {})
        except ValueError:
            self.log('Can\'t decode JSON response for search term "{}"'.format(
                response.meta.get('search_term')
            ), level=WARNING)

    @staticmethod
    def _parse_items_in_section(sections):
        items = []
        if isinstance(sections, list):
            for section in sections:
                _items = section.get('items', None) if section else None
                if not _items or not isinstance(_items, list):
                    continue
                items.extend(_items)
        return items

    @staticmethod
    def _parse_links_in_items(items):
        links = []
        if isinstance(items, list):
            for item in items:

                link = item.get('link', None)
                if not link:
                    continue

                url = link.get('url', None)
                if not url:
                    continue

                is_prime = True if item.get('shipping', {}).get('prime', {}).get('hasBadge', False) else False

                # TODO: What is pantry?
                is_prime_pantry = False

                # TODO: Implement sponsored links parsing
                is_sponsored = False

                links.append(
                    (url, is_prime, is_prime_pantry, is_sponsored)
                )
        return links
