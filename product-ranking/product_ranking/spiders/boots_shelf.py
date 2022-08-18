# -*- coding: utf-8 -*-

import re
import json
from boots import BootsProductsSpider
from scrapy.http import Request, FormRequest
from scrapy.log import ERROR, DEBUG, WARNING
import urllib
import urlparse


class BootsShelfPagesSpider(BootsProductsSpider):
    name = 'boots_shelf_urls_products'
    allowed_domains = ["boots.com", "recs.richrelevance.com"]

    NEXT_URL = 'http://www.boots.com/ProductListingView?searchType=1000&filterTerm=&langId=-1&advancedSearch=&' \
               'cm_route2Page={route}&sType=SimpleSearch&cm_pagename={pagename}&gridPosition=&metaData=&manufacturer=&' \
               'ajaxStoreImageDir=%2Fwcsstore%2FeBootsStorefrontAssetStore%2F&resultCatEntryType=&searchTerm=&' \
               'resultsPerPage=24&emsName=&facet=&categoryId={category_id}&disableProductCompare=false&filterFacet=&' \
               'productBeginIndex={begin_index}&beginIndex={begin_index}&pageNo={page_num}'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.shelf_route = ''
        self.category_id = ''
        self.category_name = ''
        self.num_pages = int(kwargs.pop('num_pages', '1'))

        super(BootsShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': '', 'remaining': self.quantity},
                      dont_filter=True)

    def _get_route(self, response):
        if not self.shelf_route:
            route = response.xpath('//div[@id="widget_breadcrumb"]//a/@title').extract()
            route = ">".join(route)
            self.shelf_route = urllib.quote_plus(">".join([route, self._get_category_name(response)]))
        return self.shelf_route

    def _get_category_id(self, response):
        if not self.category_id:
            category_id = response.xpath('//meta[@name="cmcategoryId"]/@content').extract()
            self.category_id = category_id[0] if category_id else ''
        return self.category_id

    def _get_category_name(self, response):
        if not self.category_name:
            category_name = response.xpath('//meta[@name="cmcategoryname"]/@content').extract()
            self.category_name = category_name[0] if category_name else ''
        return self.category_name

    def _scrape_total_matches(self, response):
        total = response.xpath('//span[@class="showing_products_total"]/text()').extract()
        try:
            return int(total[0])
        except:
            self.log('Failed to parse total matches count', WARNING)
            return 0

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        total = self._scrape_total_matches(response)
        count = total / 24 + 1
        begin_index = self.current_page * 24
        if self.current_page < count:
            self.current_page += 1
            url = self.NEXT_URL.format(route=self._get_route(response),
                                       pagename=self._get_category_name(response),
                                       category_id=self._get_category_id(response),
                                       begin_index=begin_index,
                                       page_num=self.current_page)

            return Request(url=url, headers={
                'X-Requested-With': 'XMLHttpRequest'
            },
                           meta={'search_term': '', 'remaining': self.quantity}, )

    def _get_next_products_page(self, response, prods_found):
        link_page_attempt = response.meta.get('link_page_attempt', 1)

        result = None
        if prods_found is not None:
            # This was a real product listing page.
            remaining = response.meta['remaining']
            remaining -= prods_found
            if remaining > 0:
                next_page = self._scrape_next_results_page_link(response)
                if next_page is None:
                    pass
                elif isinstance(next_page, Request):
                    next_page.meta['remaining'] = remaining
                    result = next_page
                else:
                    url = urlparse.urljoin(response.url, next_page)
                    new_meta = dict((k, v) for k, v in response.meta.iteritems()
                                    if k in ['remaining', 'total_matches', 'search_term',
                                             'products_per_page', 'scraped_results_per_page']
                                    )
                    new_meta['remaining'] = remaining
                    result = Request(url, self.parse, meta=new_meta, priority=1)
        elif link_page_attempt > self.MAX_RETRIES:
            self.log(
                "Giving up on results page after %d attempts: %s" % (
                    link_page_attempt, response.request.url),
                ERROR
            )
        else:
            self.log(
                "Will retry to get results page (attempt %d): %s" % (
                    link_page_attempt, response.request.url),
                WARNING
            )

            # Found no product links. Probably a transient error, lets retry.
            new_meta = response.meta.copy()
            new_meta['link_page_attempt'] = link_page_attempt + 1
            result = response.request.replace(
                meta=new_meta, cookies={}, dont_filter=True)

        return result
