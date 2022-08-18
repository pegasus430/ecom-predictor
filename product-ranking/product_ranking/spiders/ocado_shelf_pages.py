# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals
import re

from scrapy import Request

from product_ranking.utils import valid_url
from .ocado import OcadoProductsSpider
from product_ranking.items import SiteProductItem


class OcadoShelfPagesSpider(OcadoProductsSpider):
    name = 'ocado_shelf_urls_products'

    def __init__(self, *args, **kwargs):
        self.product_url = kwargs['product_url']
        self.current_page = 1
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', 1))
        self.limit_prods = int(kwargs.pop('limit_prods', 500))

        self.ads_detect = False
        ads_detect = kwargs.pop('detect_ads', False)
        if ads_detect in (1, '1', 'true', 'True', True):
            self.ads_detect = True

        super(OcadoShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        if not 'startWebshop.do' in self.product_url:
            self.product_url = self.product_url + '&itemsOnPage=' + str(self.limit_prods)
        request = Request(url=valid_url(self.product_url),
                          meta={'remaining': self.quantity,
                          'search_term': ''})

        if self.ads_detect:
            request = request.replace(callback=self._start_ads_request)

        yield request

    def _scrape_total_matches(self, response):
        totals = response.xpath('//div[@class="total-product-number"]/span/text()').extract()
        if totals:
            totals = re.findall(r'(\d+) products', totals[0])
            return int(totals[0]) if totals else None

    def _scrape_product_links(self, response):
        meta = response.meta.copy()
        items = meta.get('items')
        if not items:
            items = self._get_product_links(response)
        else:
            meta['items'] = None

        sponsored_links = meta.get('sponsored_links')

        if self.ads_detect is True and not sponsored_links:
            sponsored_links = self._get_sponsored_links(response)
        if not items and meta.get('ads'):
            items = [self.product_url]

        for item in items:
            prod_item = SiteProductItem()
            if self.ads_detect is True:
                prod_item['ads'] = meta.get('ads')
                prod_item['sponsored_links'] = sponsored_links

            req = Request(item,
                          callback=self.parse_product,
                          meta={
                              'product': prod_item,
                              'remaining': self.quantity,
                              'search_term': ''
                          },
                          dont_filter=True)

            yield req, prod_item

    def _get_product_links(self, response):
        skus = []
        links = []

        for section in self._extract_sections(response, 'js-productPageJson'):
            skus += section.get('fops', [])

        current_page = response.meta.get('current_page')
        if not current_page:
            current_page = 1
        start_idx = (current_page - 1) * self.limit_prods
        end_idx = current_page * self.limit_prods
        skus = skus[start_idx:] if len(skus) < end_idx else skus[start_idx:end_idx]

        for fop in skus:
            links.append(self.PRODUCT_URL.format(sku=fop.get('sku')))

        return links

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        current_page = meta.get('current_page')
        total_matches = self._scrape_total_matches(response)
        if not current_page:
            current_page = 1
        if total_matches <= current_page * self.limit_prods:
            return None
        current_page += 1
        next_link = self.product_url + '&itemsOnPage=' + str(current_page * self.limit_prods)
        return Request(
            next_link,
            meta={
                'search_term': "",
                'remaining': self.quantity,
                'current_page': current_page},
        )
