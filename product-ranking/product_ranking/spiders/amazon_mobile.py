# -*- coding: utf-8 -*-

import json
import urllib
import urlparse
import traceback

from scrapy.log import ERROR, WARNING
from scrapy.http import Request
from scrapy.conf import settings

from product_ranking.spiders import FormatterWithDefaults
from product_ranking.items import SiteProductItem
from product_ranking.spiders.amazon import AmazonProductsSpider


class AmazonMobileProductsSpider(AmazonProductsSpider):
    name = 'amazon_mobile_products'
    SEARCH_URL = 'https://www.amazon.com/s/ref=nb_sb_ss_sh_1_0' \
                 '?k={search_term}' \
                 '&rh=i:aps,k:{search_term}' \
                 '&page={page_num}' \
                 '&dataVersion=v0.2' \
                 '&format=json' \
                 '&cid=08e6b9c8bdfc91895ce634a035f3d00febd36433'

    def __init__(self, sort_mode='', *args, **kwargs):
        settings.overrides['DOWNLOAD_DELAY'] = 1
        settings.overrides[
            'USER_AGENT'] = 'Mozilla/5.0 (Linux; Android 7.0; SM-A510F Build/NRD90M; wv)' \
                            'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/59.0.3071.125 Mobile Safari/537.36'
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.CustomClientContextFactory'
        settings.overrides['DEFAULT_REQUEST_HEADERS'] = {
            'Host': 'www.amazon.com',
            'X-Forwarded-For': '127.0.0.1'
        }
        self.user_agent = 'Mozilla/5.0 (Linux; Android 7.0; SM-A510F Build/NRD90M; wv)' \
                          'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/59.0.3071.125 Mobile Safari/537.36'
        super(AmazonMobileProductsSpider, self).__init__(*args, **kwargs)
        self.url_formatter = FormatterWithDefaults(page_num=1)

    def _scrape_total_matches(self, response):
        try:
            return int(self._get_metadata(response).get('totalResults', 0))
        except:
            self.log('Failed to get total matches number: {}'.format(
                traceback.print_exc()), level=WARNING)

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
            prod = SiteProductItem(
                prime='Prime' if is_prime else None
            )
            yield Request(
                link,
                callback=self.parse_product,
                meta={
                    'product': prod
                },
                headers={
                    'Referer': None,
                }
            ), prod

    def _scrape_next_results_page_link(self, response):
        pagination = self._get_pagination(response)
        if pagination:
            pages = pagination.get('pages', None)
            if pages and isinstance(pages, list):
                for page in pages:
                    if page.get('type', None) == u'next':
                        next_num = page.get('page')
                        if next_num:
                            return self.SEARCH_URL.format(search_term=response.meta.get('search_term'),
                                                          page_num=next_num)
        return None

    def _get_metadata(self, response):
        try:
            return json.loads(response.body, encoding='utf-8').get('resultsMetadata', {})
        except ValueError:
            self.log('Can\'t decode JSON response for search term "{}"'.format(
                response.meta.get('search_term')
            ), level=ERROR)

    def _get_sections(self, response):
        try:
            return json.loads(response.body, encoding='utf-8').get('results', {}).get('sections', [])
        except ValueError:
            self.log('Can\'t decode JSON response for search term "{}"'.format(
                traceback.print_exc()
            ), level=WARNING)

    def _get_pagination(self, response):
        try:
            return json.loads(response.body, encoding='utf-8').get('pagination', {})
        except:
            self.log('Can\'t decode JSON response: {}'.format(
                traceback.print_exc()
            ), level=WARNING)

    @staticmethod
    def _parse_items_in_section(sections):
        items = []
        if isinstance(sections, list):
            for section in sections:
                if section:
                    _items = section.get('items', None)
                    if not _items or not isinstance(_items, list):
                        continue
                    items += _items
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

                is_prime = bool(item.get('shipping', {}).get('prime', {}).get('hasBadge', False))

                is_prime_pantry = False

                # TODO: Implement sponsored links parsing
                is_sponsored = False

                links.append(
                    (url, is_prime, is_prime_pantry, is_sponsored)
                )
        return links
