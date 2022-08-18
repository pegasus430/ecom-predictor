# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals

import json
from urlparse import urljoin
from lxml import html
from urllib import urlencode

from scrapy import Request
from .amazon import AmazonProductsSpider


class PantryAmazonProductsSpider(AmazonProductsSpider):
    name = "pantry_amazon_products"
    allowed_domains = ["amazon.com"]

    SEARCH_URL = 'https://www.amazon.com/s/ref=nb_sb_noss' \
                 '?url=search-alias%3Dpantry' \
                 '&field-keywords={search_term}'

    def __init__(self, *args, **kwargs):
        super(PantryAmazonProductsSpider, self).__init__(*args, **kwargs)
        detect_ads = kwargs.pop('detect_ads', False)
        self.detect_ads = detect_ads in (1, '1', 'true', 'True', True)

    def start_requests(self):
        for request in super(PantryAmazonProductsSpider, self).start_requests():
            if not self.product_url and self.detect_ads:
                request = request.replace(callback=self._get_ads_links)
            yield request

    def _get_ads_links(self, response):
        ads_xpath = '//div[@id="centerPlus"]//div[@id="desktop-auto-sparkle-single"]/a'
        ads_links = response.xpath(ads_xpath + '/@href').extract()
        ads_images = response.xpath(ads_xpath + '/img/@src').extract()
        prod_links = list(self._scrape_product_links(response))
        total_maches = self._scrape_total_matches(response)
        next_page_link = self._scrape_next_results_page_link(response)
        ads = [{
                'ad_url': urljoin(response.url, ad_url),
                'ad_image': ads_images[i],
                'ad_dest_products': []
            } for i, ad_url in enumerate(ads_links)]

        meta = response.meta.copy()
        if ads and prod_links:
            meta['ads'] = ads
            meta['prod_links'] = prod_links
            meta['total_matches'] = total_maches
            meta['next_page_link'] = next_page_link
            meta['idx'] = 0
            return Request(
                url=ads[0]['ad_url'],
                callback=self._parse_ads_links,
                meta=meta
            )
        return self.parse(response)

    def _parse_ads_links(self, response):
        meta = response.meta.copy()
        url = meta.get('url')
        body = meta.get('body', {})
        asins = meta.get('asins', [])
        if any([not asins, not body, not url]):
            carousel_options = response.xpath('//div/@data-a-carousel-options').extract()
            for carousel in carousel_options:
                try:
                    item = json.loads(carousel)
                    if not url:
                        url = item.get('ajax', {}).get('url')
                    if not body:
                        body = item.get('ajax', {}).get('params', {})
                    asins += item.get('ajax', {}).get('id_list', [])
                except:
                    self.log('carousel: {}'.format(carousel))
                    continue
        if all([url, body, asins]):
            meta['url'] = url
            meta['asins'] = asins[100:] if len(asins) > 100 else None
            meta['body'] = body
            if len(asins) > 100:
                asins = asins[:100]
            body['asins'] = ','.join(asins)
            url = '?'.join([url, urlencode(body)])
            return Request(
                url=urljoin(response.url, url),
                callback=self._parse_ads_products,
                meta=meta
            )
        return self.parse(response)

    def _parse_ads_products(self, response):
        idx = response.meta.get('idx')
        ads = response.meta.get('ads')
        try:
            products = json.loads(response.body)
        except:
            return self.parse(response)
        for product in products:
            content = product.get('content')
            try:
                content = html.fromstring(content)
                links = content.xpath(
                    '//div[contains(@class, "p-prod-tile-title")]//a[contains(@class, "a-link-normal")]/@href')
                titles = content.xpath(
                    '//div[contains(@class, "p-prod-tile-title")]//a[contains(@class, "a-link-normal")]/@title')
                if titles and links:
                    ads[idx]['ad_dest_products'].append({
                        'name': titles[0],
                        'url': urljoin(response.url, links[0])
                    })
            except:
                self.log('content: {}'.format(content))
                continue

        response.meta['ads'] = ads
        if response.meta.get('asins', []):
            return self._parse_ads_links(response)

        if idx + 1 < len(ads):
            idx += 1
            response.meta['idx'] = idx
            return Request(
                url=ads[idx]['ad_url'],
                meta=response.meta,
                callback=self._parse_ads_links
            )
        return self.parse(response)

    def _scrape_product_links(self, response):
        meta = response.meta.copy()
        prod_links = meta.get('prod_links', [])
        ads = meta.get('ads', [])
        if not prod_links:
            prod_links = list(super(PantryAmazonProductsSpider, self)._scrape_product_links(response))

        for (link, prod) in prod_links:
            if self.detect_ads and ads:
                prod['ads'] = ads
            yield link, prod

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        next_req = response.meta.get('next_page_link')
        if not next_req:
            return super(PantryAmazonProductsSpider, self)._scrape_next_results_page_link(response)

        meta['next_page_link'] = None
        return next_req.replace(meta=meta)

    def _scrape_total_matches(self, response):
        count_matches = self._is_empty(
            response.xpath(
                '//*[@id="s-result-count"]/text()'
            ).re(unicode(self.total_matches_re))
        )
        total_matches = self._get_int_from_string(count_matches)

        return total_matches