# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import json
import traceback

from .nike import NikeProductSpider
from scrapy.http import Request
from product_ranking.items import SiteProductItem
from product_ranking.utils import is_empty


class NikeShelfPagesSpider(NikeProductSpider):
    name = 'nike_shelf_urls_products'
    allowed_domains = ["nike.com"]

    PRODUCTS_URL = "http://store.nike.com/html-services/gridwallData?country=US&lang_locale=en_US" \
                   "&gridwallPath={category_name}/{category_id}&pn={page_number}&segments=viewall"

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))

        super(NikeShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        return {'remaining': self.quantity, 'search_term': ''}.copy()

    def _parse_category(self):
        try:
            url_splits = self.product_url.split('/')
            category_name = url_splits[-2].strip()
            category_id = url_splits[-1].split('?')[0].strip()
        except Exception as e:
            self.log('Error while parsing category {}'.format(traceback.format_exc(e)))
            category_name = None
            category_id = None

        return category_name, category_id

    def start_requests(self):
        if self.product_url:
            yield Request(
                self.product_url,
                meta=self._setup_meta_compatibility()
            )

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            products = data['sections'][0].get('products', [])
            for product in products:
                yield product.get('pdpUrl'), SiteProductItem()
        except Exception as e:
            self.log('Invalid JSON: {}'.format(traceback.format_exc(e)))
            links = response.xpath(
                "//div[contains(@class, 'grid-item')]"
                "//div[contains(@class, 'grid-item-image-wrapper')]"
                "//a/@href").extract()

            for link in links:
                item = SiteProductItem()
                yield Request(
                    link,
                    callback=self.parse_product,
                    meta={'product': item}), item

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            total_matches = data['navigation']['totalRecords']
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()))
            total_matches = is_empty(response.xpath(
                '//*[contains(@class, "exp-gridwall-title")]'
                '//span[@class="nsg-text--medium-light-grey"]'
                '/text()').re(r'\d+'), '0')

        return int(total_matches)

    def _scrape_next_results_page_link(self, response):
        if list(self._scrape_product_links(response)) and self.current_page < self.num_pages:
            self.current_page += 1

            try:
                data = json.loads(response.body_as_unicode())
                next_page = data.get('nextPageDataService')
            except Exception as e:
                self.log('Error while parsing next page link: {}'.format(traceback.format_exc(e)))
                category_name, category_id = self._parse_category()
                if not category_name or not category_id:
                    return None

                next_page = self.PRODUCTS_URL.format(
                    category_name=category_name,
                    category_id=category_id,
                    page_number=self.current_page
                )

            return next_page
