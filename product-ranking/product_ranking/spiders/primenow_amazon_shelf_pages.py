from __future__ import absolute_import, division, unicode_literals

import urlparse
import re

from lxml import html
from product_ranking.items import SiteProductItem
from scrapy.http import Request
from product_ranking.spiders.primenow_amazon import \
    PrimenowAmazonProductsSpider


class PrimenowAmazonShelfPagesSpider(PrimenowAmazonProductsSpider):
    name = 'primenow_amazon_shelf_urls_products'

    HEADERS = {"Upgrade-Insecure-Requests": "1",
               "Referer": "https://primenow.amazon.com/",
               "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
               "Accept-Encoding": "gzip, deflate, br",
               "Accept-Language": "en-US,en;q=0.9",
               "Cache-Control": "max-age=0",
               "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.89 Safari/537.36"
               }

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))

        self.detect_shelf_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', 'on', True):
            self.detect_shelf_ads = True
        super(PrimenowAmazonShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _start_requests(self, response):
        if self.product_url:
            request = Request(self.product_url,
                              meta={'search_term': '',
                                    'remaining': self.quantity}
                              )
            if self.detect_shelf_ads:
                request = request.replace(callback=self._start_ads_request)

            yield request

    def _scrape_total_matches(self, response):
        meta = response.meta.copy()
        totals = meta.get('totals')
        if not totals:
            totals = self._parse_total_matches(response)
        return totals

    def _scrape_product_links(self, response):
        meta = response.meta.copy()
        items = meta.get('items')
        if not items:
            items = self._get_product_links(response)
        else:
            meta['items'] = None

        sponsored_links = meta.get('sponsored_links')
        st = meta.get('search_term')

        if self.detect_shelf_ads is True and not sponsored_links:
            sponsored_links = self._get_sponsored_links(response)

        if items:
            for item in items:
                prod_item = SiteProductItem()
                if self.detect_shelf_ads is True:
                    prod_item['ads'] = meta.get('ads')
                    prod_item['sponsored_links'] = sponsored_links

                req = Request(
                    url=item,
                    headers=self.HEADERS,
                    callback=self.parse_product,
                    meta={
                        "product": prod_item,
                        'search_term': st,
                        'remaining': self.quantity,
                    },
                    dont_filter=True
                )
                yield req, prod_item
        else:
            self.log("Found no product links in {url}".format(url=response.url))

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1

        meta = response.meta.copy()

        next_link = meta.get('next_link')
        if not next_link:
            next_link = self._parse_next_page_link(response)
        if next_link:
            return next_link

    def _get_ads_path(self):
        return '//div[@class="category-tile-image"]//a'

    @staticmethod
    def _get_product_links(response):
        links = []
        items = response.xpath("//a[contains(@class, 'asin_card__productLink')]/@href").extract()

        for item in items:
            links.append(urlparse.urljoin(response.url, item))
        return links

    def _get_product_names(self, response):
        item_names = []
        items = response.xpath("//div[@id='house-search-result']//a[@class='a-link-normal asin_card_dp_link a-text-normal']//p/text()").extract()
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
                featured_links.append(html.fromstring(item).xpath('.//div[@class="fop-item"]//div[contains(@class, "fop-content-wrapper")]//a/@href'))
            if is_featured:
                featured_links.append(html.fromstring(item).xpath('.//div[@class="fop-item"]//div[contains(@class, "fop-content-wrapper")]//a/@href'))

        for links in featured_links:
            for link in links:
                if not 'javascript' in link:
                    sponsored_links.append(urlparse.urljoin(response.url, link))
        return sponsored_links

    def _parse_total_matches(self, response):
        total_info = response.xpath(
            "//div[contains(@class, 'grid-header-label')]"
            "//h2[@id='house-normal-result-label']"
            "//text()").extract()
        if total_info:
            total = re.findall(r'\d+', ''.join(total_info))
        else:
            total = 0

        if total:
            total_matches = int(total[0])
        else:
            total_matches = 0
        return total_matches if total_matches else 0

    def _parse_next_page_link(self, response):
        next_page_link = response.xpath(
            "//div[@id='house-search-pagination']//li[contains(@class, 'a-last')]//a/@href").extract()
        if next_page_link:
            return urlparse.urljoin(response.url, next_page_link[0])

    def _start_ads_request(self, response):
        meta = response.meta.copy()
        ads = []

        ads_urls = []
        image_urls = []
        ads_xpath = self._get_ads_path()
        ads_urls.extend([urlparse.urljoin(response.url, ad) for ad in response.xpath(ads_xpath + '/@href').extract()])
        image_urls.extend([urlparse.urljoin(response.url, ad) for ad in response.xpath(ads_xpath + '//img/@src').extract()])

        items = self._get_product_links(response)
        totals = self._parse_total_matches(response)
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

    def _parse_ads_product(self, response):
        ads = response.meta.get('ads', [])
        ads_idx = response.meta.get('ads_idx')
        ads_urls = response.meta.get('ads_urls')
        next_link = self._parse_next_page_link(response)

        product_links = self._get_product_links(response)
        product_names = self._get_product_names(response)
        if product_links:
            products = [{
                            'url': product_links[i],
                            'name': product_names[i],
                        } for i in range(len(product_links))]
            if ads[ads_idx].get('ad_dest_products', {}):
                ads[ads_idx]['ad_dest_products'] += products
            else:
                ads[ads_idx]['ad_dest_products'] = products

        response.meta['ads'] = ads

        if next_link:
            return Request(
                url=next_link,
                meta=response.meta,
                callback=self._parse_ads_product,
                dont_filter=True
                )

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