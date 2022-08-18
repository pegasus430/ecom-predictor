# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals
from urlparse import urljoin

from .jumbo import JumboProductsSpider
from scrapy.http import Request
from scrapy.log import INFO

from product_ranking.items import SiteProductItem
from product_ranking.utils import valid_url

class JumboShelfPagesSpider(JumboProductsSpider):
    name = 'jumbo_shelf_urls_products'
    allowed_domains = ["jumbo.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))
        self.detect_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_ads = True

        super(JumboShelfPagesSpider, self).__init__(*args, **kwargs)

    def _start_requests(self, response):
        meta = response.meta.copy()
        store = meta.get('store')
        zip_code = meta.get('zip_code')
        request = Request(
            url=valid_url(self.product_url),
            meta={
                'search_term': '',
                'remaining': self.quantity,
                'store': store,
                'zip_code': zip_code
            }
        )
        if self.detect_ads:
            request = request.replace(callback=self._get_ads_urls)
        yield request

    def _scrape_total_matches(self, response):
        return None

    @staticmethod
    def _get_product_links(response):
        items = response.xpath('//dt[@class="jum-item-title"]//a/@href').extract()
        return items

    @staticmethod
    def _get_product_names(response):
        items = response.xpath('//*[@data-jum-action="ellipsis"]'
                               '/a/text()').extract()
        return items

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        meta = response.meta.copy()
        ads_dest_products = meta.get('ads_dest_products')
        ads_urls = meta.get('ads_urls')
        items = meta.get('items')
        image_urls = meta.get('image_urls')
        if not items:
            items = self._get_product_links(response)
        else:
            meta['items'] = None

        if items:
            for item in items:
                res_item = SiteProductItem()

                if ads_urls:
                    res_item['ads_urls'] = ads_urls
                    res_item['ads_dest_products'] = ads_dest_products
                    res_item['ads_count'] = len(ads_urls)
                    res_item['ads_images'] = image_urls
                res_item['store'] = meta.get('store')
                res_item['zip_code'] = meta.get('zip_code')
                yield item, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        items = meta.get('items')
        if not items:
            items = self._get_product_links(response)
        else:
            meta['items'] = None
        current_page = meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return
        if self.detect_ads:
            url = meta.get('category_url')
        else:
            url = self._get_next_page_template(response)
        url = url.replace('?PageNumber=N', '?PageNumber=' + str(current_page)) if url else None
        meta['current_page'] = current_page + 1
        if items and url:
            return Request(
                url=url,
                meta=meta,
                cookies=self.cookies,
                dont_filter=True,
            )

    def _get_ads_urls(self, response):
        meta = response.meta.copy()

        ads_xpath = '//aside//div[@data-endeca-component="IntershopContent"]//a[contains(@href, "producten")]'
        ads_urls = response.xpath(ads_xpath + '/@href').extract()
        image_urls = response.xpath(ads_xpath + '//img/@src').extract()
        ads_urls = [urljoin(response.url, i) for i in ads_urls]
        image_urls = [urljoin(response.url, i) for i in image_urls]
        items = self._get_product_links(response)
        meta['items'] = items
        category_url = self._get_next_page_template(response)
        meta['category_url'] = category_url if category_url else None

        if ads_urls and items:
            meta['ads_idx'] = 0
            meta['image_urls'] = image_urls
            meta['ads_urls'] = ads_urls
            meta['ads_dest_products'] = []
            meta['current_page'] = 1
            return Request(
                url=ads_urls[0],
                meta=meta,
                callback=self._scrape_products_of_ads,
                cookies=self.cookies,
                dont_filter=True,
            )
        else:
            return self.parse(response)

    @staticmethod
    def _get_next_page_template(response):
        next_page_template = response.xpath('//div[@class="ws-product-listing-pagination"]'
                                            '/@data-jum-pagination-link-template').extract()
        return next_page_template[0] if next_page_template else None

    def _scrape_products_of_ads(self, response):
        ads_idx = response.meta.get('ads_idx')
        ads_urls = response.meta.get('ads_urls')
        ads_dest_products = response.meta.get('ads_dest_products')
        current_page = response.meta.get('current_page')

        product_links = self._get_product_links(response)
        product_names = self._get_product_names(response)
        link = None

        if product_links:
            products = [{
                            'product_name': product_names[i],
                            'url': product_links[i]
                        } for i in range(len(product_links))]

            ads_dest_products += products
            if current_page == 1:
                page_link = self._get_next_page_template(response)
                link = page_link.replace('PageNumber=N', 'PageNumber=' + str(current_page)) if page_link else None
            else:
                link = response.url.replace('?PageNumber=' + str(current_page-1), '?PageNumber=' + str(current_page))
            response.meta['current_page'] = current_page + 1
            response.meta['ads_dest_products'] = ads_dest_products
        if len(product_links) < 12 or not link:
            ads_idx += 1
            response.meta['current_page'] = 1
            if ads_idx < len(ads_urls):
                link = ads_urls[ads_idx]
            else:
                return self.parse(response)
        return Request(
            url=link,
            meta=response.meta,
            callback=self._scrape_products_of_ads,
            cookies=self.cookies,
            dont_filter=True
        )
