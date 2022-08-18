# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import urlparse

import re
from lxml import html
from scrapy import Selector
from product_ranking.items import SiteProductItem
from product_ranking.spiders.groceries_morrisons import GroceriesMorrisonsProductsSpider
from scrapy import Request


class GroceriesMorrisonsShelfPagesSpider(GroceriesMorrisonsProductsSpider):
    name = 'groceries_morrisons_shelf_urls_products'

    CATEGORY_URL = 'https://groceries.morrisons.com/webshop/getCategories.do?' \
                   'tags={category_tag}&viewAllProducts=true&recommendations=true&format=json'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.results_per_page = 20
        self.num_pages = int(kwargs.pop('num_pages', '1'))

        super(GroceriesMorrisonsShelfPagesSpider, self).__init__(*args, **kwargs)

        self.detect_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', 'on', True):
            self.detect_ads = True

    def start_requests(self):
        cookies = {
            'TC': "d4bd1e59-684c-40cd-8ce7-0382ca492efd"
        }
        request = Request(url=self.product_url,
                          meta={'search_term': "", 'remaining': self.quantity},
                          callback=self._start_shelf,
                          cookies=cookies,
                          dont_filter=True
                          )
        if self.detect_ads:
            request = request.replace(callback=self._start_ads_request)

        yield request

    def _start_shelf(self, response):
        total_matches = self._scrape_total_matches(response)
        category_tag = response.xpath("//input[@name='tags']/@value").extract()
        if category_tag:
            response.meta['tag'] = category_tag[0].strip()
            return Request(
                url=self.CATEGORY_URL.format(category_tag=category_tag[0].strip()),
                callback=self.parse,
                meta=response.meta,
                dont_filter=True
            )

    def _scrape_total_matches(self, response):
        totals = response.meta.get('totals')
        if not totals:
            totals = self._parse_total_matches(response)
            response.meta['totals'] = totals
        return totals

    def _scrape_product_links(self, response):
        meta = response.meta.copy()
        items = meta.get('items')
        if not items:
            items = self._get_product_links(response)

        if items:
            for item in items:
                prod_item = SiteProductItem()
                yield item, prod_item
        else:
            self.log("Found no product links in {url}".format(url=response.url))

    def _parse_total_matches(self, response):
        total = response.xpath("//span[@class='show-for-xlarge']").re('\d+')
        return int(total[0]) if total else None

    def _get_ads_path(self):
        return '//div[@data-element-type="promotion"]//div[@class="cornerBox"]//a | ' \
               '//div[@class="supFund"]//a'

    @staticmethod
    def _get_product_links(response):
        links = []
        items = response.xpath('//div[contains(@class, "fop-content-wrapper")]/a/@href').extract()
        if not items:
            items = response.xpath('//h4[@class="productTitle"]/a/@href').extract()
        for item in items:
            if '/webshop/' in item:
                links.append(urlparse.urljoin(response.url, item))
        return links

    def _get_product_names(self, response):
        item_names = []
        items = response.xpath("//h4[@class='fop-title']/text()").extract()
        for item in items:
            item_names.append(self._clean_text(item))
        return item_names

    @staticmethod
    def _get_sponsored_links(response):
        is_featured = False
        featured_links = []
        sponsored_links = []
        items = response.xpath("//div[@id='js-productPageFops']//li").extract()
        for item in items:
            if 'featured' in item:
                is_featured = True
            if 'last' in item:
                is_featured = False
                featured_links.append(html.fromstring(item).xpath(
                    './/div[@class="fop-item"]//div[contains(@class, "fop-content-wrapper")]//a/@href'))
            if is_featured:
                featured_links.append(html.fromstring(item).xpath(
                    './/div[@class="fop-item"]//div[contains(@class, "fop-content-wrapper")]//a/@href'))

        for links in featured_links:
            for link in links:
                if not 'javascript' in link:
                    sponsored_links.append(urlparse.urljoin(response.url, link))
        return sponsored_links

    def _start_ads_request(self, response):
        meta = response.meta.copy()
        ads = []

        ads_urls = []
        image_urls = []
        ads_xpath = self._get_ads_path()
        for ad in response.xpath(ads_xpath + '/@href').extract():
            if 'href=' in ad:
                ad = Selector(text=ad).xpath('//a/@href').extract()
                if ad:
                    ad = ad[0]
            ads_urls.extend([urlparse.urljoin(response.url, ad)])
        for ad in response.xpath(ads_xpath + '//img/@src').extract():
            if 'href=' in ad:
                ad = Selector(text=ad).xpath('//img/@src').extract()
                if ad:
                    ad = ad[0]
            image_urls.extend(
                [urlparse.urljoin(response.url, ad)])

        category_tag = response.xpath("//input[@name='tags']/@value").extract()
        if category_tag:
            response.meta['tag'] = category_tag[0].strip()

        items = self._get_product_links(response)
        totals = self._parse_total_matches(response)

        meta['totals'] = totals
        meta['items'] = items

        sponsored_links = self._get_sponsored_links(response)
        meta['sponsored_links'] = sponsored_links

        for i, url in enumerate(ads_urls):
            ad = {
                'ad_url': url,
                'ad_image': image_urls[i]
            }
            ads.append(ad)
        if ads_urls and items:
            meta['ads_idx'] = 0
            meta['image_urls'] = image_urls
            meta['ads_urls'] = ads_urls
            meta['ads'] = ads

            return Request(
                url=ads_urls[0],
                meta=meta,
                callback=self._parse_ads_product,
                dont_filter=True,
            )

    def _parse_ads_product(self, response):
        ads = response.meta.get('ads', [])
        ads_idx = response.meta.get('ads_idx')
        ads_urls = response.meta.get('ads_urls')

        product_links = self._get_product_links(response)
        product_names = self._get_product_names(response)
        if product_links:
            products = [{
                'url': product_links[i],
                'name': product_names[i],
            } for i in range(len(product_links))]

            ads[ads_idx]['ad_dest_products'] = products
        response.meta['ads'] = ads

        ads_idx += 1
        if ads_idx < len(ads_urls):
            link = ads_urls[ads_idx]
            response.meta['ads_idx'] += 1
        else:
            return self._scrape_ads_links(response)

        return Request(
            url=link,
            meta=response.meta,
            callback=self._parse_ads_product,
            dont_filter=True
        )

    def _scrape_ads_links(self, response):
        meta = response.meta.copy()

        sponsored_links = meta.get('sponsored_links')

        if not sponsored_links:
            sponsored_links = self._get_sponsored_links(response)

        prod_item = SiteProductItem()
        prod_item['ads'] = meta.get('ads')
        prod_item['sponsored_links'] = sponsored_links

        yield prod_item

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()
