# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

import re
import json
import urlparse

from scrapy.conf import settings
from scrapy.http import Request
from .minibardelivery import MinibarDeliveryProductsSpider


class MinibarDeliveryShelfPagesSpider(MinibarDeliveryProductsSpider):
    name = 'minibardelivery_shelf_urls_products'

    CATEGORY_URL_1 = "https://minibardelivery.com/api/v2/supplier/{supplier_ids}/product_groupings" \
                     "?hierarchy_category={hrc_category}&hierarchy_type[]={hrc_type}&base=hierarchy_type" \
                     "&sort=popularity&sort_direction=desc&facet_list[]=hierarchy_subtype&facet_list[]=country" \
                     "&facet_list[]=price&page={page_number}&per_page=20&shipping_state=CA"

    CATEGORY_URL_2 = "https://minibardelivery.com/api/v2/supplier/{supplier_ids}/product_groupings" \
                     "?hierarchy_category={hrc_category}&base=hierarchy_category&sort=popularity&sort_direction=desc" \
                     "&facet_list[]=hierarchy_type&facet_list[]=hierarchy_subtype&page={page_number}" \
                     "&per_page=20&shipping_state=CA"

    SUPPLIERS_URL = 'https://minibardelivery.com/api/v2/suppliers?address_id=&coords[latitude]=37.7800851' \
                    '&coords[longitude]=-122.39460170000001&address[address1]=400 Brannan Street' \
                    '&address[city]=San Francisco&address[state]=CA&address[zip_code]=94107' \
                    '&routing_options[defer_load]=true&defer_load=true'

    ITEMS_LIMITS = 500

    download_delay = 1

    result_per_page = 20

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))

        retry_codes = settings.get('RETRY_HTTP_CODES')
        retry_codes += [403]
        settings.overrides['RETRY_HTTP_CODES'] = retry_codes

        super(MinibarDeliveryShelfPagesSpider, self).__init__(*args, **kwargs)

    def _start_requests(self, response):
        ids = []
        suppliers = json.loads(response.body).get('suppliers', [])
        for supplier in suppliers:
            ids.append(str(supplier.get('id', [])))

        if not ids:
            return

        ids = ','.join(ids)
        scheme, netloc, url, params, query, fragment = urlparse.urlparse(self.product_url)
        categories = url.replace('/store/category/', '').split('/')

        hierarchy_category = hierarchy_type = None
        if len(categories) > 1:
            hierarchy_category = categories[0]
            hierarchy_type = categories[1]
        elif len(categories) == 1:
            hierarchy_category = categories[0]

        if not hierarchy_category:
            return

        if hierarchy_type:
            req_url = self.CATEGORY_URL_1.format(
                supplier_ids=ids,
                page_number=self.current_page,
                hrc_category=hierarchy_category,
                hrc_type=hierarchy_type
            )
        else:
            req_url = self.CATEGORY_URL_2.format(
                supplier_ids=ids,
                page_number=self.current_page,
                hrc_category=hierarchy_category
            )

        yield Request(
            url=req_url,
            meta={'search_term': '', 'remaining': self.quantity, 'supplier_ids': ids},
            headers=self.HEADER
        )

    def _scrape_next_results_page_link(self, response):
        if self.current_page * self.result_per_page > self.total_matches:
            return

        if self.current_page * self.result_per_page > self.ITEMS_LIMITS:
            return

        self.current_page += 1
        meta = response.meta.copy()
        next_page = re.sub(r'&page=(\d+)&', "&page={}&".format(self.current_page), response.url)

        return Request(next_page, meta=meta, headers=self.HEADER)
