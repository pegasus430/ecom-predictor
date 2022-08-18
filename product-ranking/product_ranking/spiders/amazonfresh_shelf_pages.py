from __future__ import division, absolute_import, unicode_literals

from .amazonfresh import AmazonFreshProductsSpider
from scrapy.http import Request
import urlparse

from product_ranking.items import SiteProductItem
from product_ranking.utils import is_empty


class AmazonFreshShelfPagesSpider(AmazonFreshProductsSpider):
    name = 'amazonfresh_shelf_urls_products'
    allowed_domains = ["www.amazon.com"]
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/60.0.3112.78 Safari/537.36"}

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(AmazonFreshShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

        self.detect_shelf_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_shelf_ads = True

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}.copy()

    def start_requests(self):
        request = Request(url=self.product_url,
                          meta=self._setup_meta_compatibility(),
                          headers=self.headers)

        if self.detect_shelf_ads:
            request = request.replace(callback=self._start_ads_requests)

        yield request

    def _scrape_total_matches(self, response):
        total_matches = response.xpath('//h2[@id="s-result-count"]/text()').re('(\d+) results')

        if total_matches:
            return int(total_matches[0])

    def _scrape_product_links(self, response):
        meta = response.meta.copy()
        items = meta.get('items', [])
        if not items:
            items = self._get_product_links(response)
        else:
            meta['items'] = None

        sponsored_links = meta.get('sponsored_links')
        if self.detect_shelf_ads is True and not sponsored_links:
            sponsored_links = self._get_sponsored_links(response)

        for link in items:
            prod_item = SiteProductItem()
            if self.detect_shelf_ads is True:
                prod_item['ads'] = meta.get('ads')
                prod_item['sponsored_links'] = sponsored_links

            req = Request(
                url=link,
                callback=self.parse_product,
                headers={'Referer': None},
                meta={
                    "product": prod_item
                },
                dont_filter=True
            )

            yield req, prod_item

    def _scrape_next_results_page_link(self, response):
        if self.current_page < self.num_pages:
            self.current_page += 1

            return super(AmazonFreshShelfPagesSpider, self)._scrape_next_results_page_link(response)

    def _get_ads_path(self):
        return ["//div[@class='acs-shwcs-image-single']//a",
                "//div[@class='acsUxWidget']//div[contains(@class, 'bxc-grid__column--12-of-12')]"
                "//div[contains(@class, 'bxc-grid__image')]//a"]

    def _get_product_links(self, response):
        links = []
        ul = response.xpath('//li[contains(@class, "s-result-item")]')
        if not ul:
            return
        for li in ul:
            link = is_empty(li.xpath(
                './/a[contains(@class, "s-access-detail-page")]/@href'
            ).extract())
            if not link:
                continue

            links.append(link)

        return links

    def _get_sponsored_links(self, response):
        sponsored_links = response.xpath("//li[contains(@class, 'a-carousel-card')]"
                                         "//a[contains(@class, 'acs_product-image')]/@href").extract()

        return [urlparse.urljoin(response.url, sponsored_link) for sponsored_link in sponsored_links]

    def _get_products_info(self, response):
        items = []
        special_product_info = []
        product_info = response.xpath("//a[contains(@class, 's-access-detail-page')]")
        if not product_info:
            special_product_info = response.xpath("//div[@class='a-carousel-viewport']")
        if special_product_info:
            product_info = special_product_info[0].xpath(".//a[contains(@class, 'a-size-small')]")
        for prod in product_info:
            item = {}
            item['name'] = ''.join(prod.xpath("./@title").extract())
            item['url'] = ''.join(prod.xpath("./@href").extract())
            items.append(item)

        return items

    def _parse_ads_product(self, response):
        ads = response.meta.get('ads', [])
        ads_idx = response.meta.get('ads_idx')
        ads_urls = response.meta.get('ads_urls')

        products_info = self._get_products_info(response)
        if products_info:
            products = [
                {
                    'url': item['url'],
                    'name': item['name'],
                } for item in products_info
            ]

            ads[ads_idx]['ad_dest_products'] = products
        response.meta['ads'] = ads

        ads_idx += 1
        if ads_idx < len(ads_urls):
            link = ads_urls[ads_idx]
            response.meta['ads_idx'] += 1
        else:
            return self.parse(response)

        return Request(
            url=link,
            meta=response.meta,
            callback=self._parse_ads_product,
            dont_filter=True
        )

    def _start_ads_requests(self, response):
        meta = response.meta.copy()
        ads = []

        ads_urls = []
        image_urls = []
        for ads_xpath in self._get_ads_path():
            ads_urls.extend([urlparse.urljoin(response.url, ad) for ad in response.xpath(ads_xpath + '/@href').extract()])
            image_urls.extend([urlparse.urljoin(response.url, ad) for ad in response.xpath(ads_xpath + '//img/@src').extract()])

        items = self._get_product_links(response)
        totals = self._scrape_total_matches(response)
        next_link = self._parse_next_page_link(response)
        meta['totals'] = totals
        meta['next_link'] = next_link
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
        else:
            return self.parse(response)

    def _parse_next_page_link(self, response):
        next_page = response.xpath('//span[@class="pagnRA"]/a[@class="pagnNext"]'
                                   '/@href').extract()
        if next_page:
            next_page = urlparse.urljoin(response.url, next_page[0])
            return next_page

