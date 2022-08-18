from __future__ import absolute_import, division, unicode_literals

import urlparse
import re
import traceback

from scrapy.http import Request
from product_ranking.utils import valid_url
from product_ranking.items import SiteProductItem
from scrapy.log import WARNING
from product_ranking.spiders.amazon_shelf_pages import AmazonShelfPagesSpider
from product_ranking.utils import is_empty
from product_ranking.spiders.amazoncouk import AmazonProductsSpider


class AmazonCoUkShelfPagesSpider(AmazonProductsSpider):
    name = 'amazoncouk_shelf_urls_products'
    allowed_domains = ["www.amazon.co.uk", "amazon.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))
        self.num_pages = min(10, self.num_pages)
        self.detect_shelf_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_shelf_ads = True

        super(AmazonCoUkShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def start_requests(self):
        request = Request(
            url=valid_url(self.product_url),
            meta={'search_term': '', 'remaining': self.quantity}
        )
        if self.detect_shelf_ads:
            request = request.replace(callback=self._get_ads_product)
        if self.is_fresh:
            request = request.replace(cookies=self.fresh_cookies)
        yield request

    def _scrape_total_matches(self, response):
        meta = response.meta.copy()
        totals = meta.get('totals')
        if not totals:
            totals = self._parse_total_matches(response)
        return totals

    def _parse_total_matches(self, response):
        total_xpath = '//*[self::h1 or self::h2 or self::h3 or self::span][@id="s-result-count"]/text()'
        try:
            total_matches = is_empty(response.xpath(total_xpath).extract())
            total_matches = re.findall(r'\d+', total_matches.replace(',', ''))
            return int(total_matches[-1])
        except:
            self.log("Found no total matches {}".format(traceback.format_exc()))
            return 0

    def _scrape_product_links(self, response):
        meta = response.meta.copy()
        items = meta.get('items')
        if not items:
            items = self._get_product_links(response)
        else:
            meta['items'] = None

        sponsored_links = meta.get('sponsored_links')
        st = meta.get('search_term')

        if self.detect_ads is True and not sponsored_links:
            sponsored_links = self._get_sponsored_links(response)

        if items:
            for link, is_prime, is_prime_pantry, is_sponsored in items:
                prime = None
                if is_prime:
                    prime = 'Prime'
                if is_prime_pantry:
                    prime = 'PrimePantry'
                prod_item = SiteProductItem(prime=prime)
                if self.detect_shelf_ads is True:
                    prod_item['ads'] = meta.get('ads')
                    prod_item['sponsored_links'] = sponsored_links
                link = re.sub(r"https?://www.amazon", "https://www.amazon", link)

                req = Request(
                    url=link,
                    callback=self.parse_product,
                    headers={'Referer': None},
                    meta={
                        "product": prod_item,
                        'search_term': st,
                        'remaining': self.quantity,
                    },
                    dont_filter=True
                )
                yield req, prod_item

    def _get_ads_product(self, response):
        meta = response.meta.copy()
        ads = []

        ads_urls = []
        image_urls = []
        for ads_xpath in self._get_ads_path():
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

    def _get_product_links(self, response):
        lis = response.xpath(
            "//div[@id='resultsCol']/./ul/li |"
            "//div[@id='mainResults']/.//ul/li [contains(@id, 'result')] |"
            "//div[@id='atfResults']/.//ul/li[contains(@id, 'result')] |"
            "//div[@id='mainResults']/.//div[contains(@id, 'result')] |"
            "//div[@id='btfResults']//ul/li[contains(@id, 'result')] |"
            "//div[@id='search-results']//ul/li[contains(@id, 'result')]")
        links = []
        last_idx = -1

        for li in lis:
            is_prime = li.xpath(
                "*/descendant::i[contains(concat(' ', @class, ' '),"
                "' a-icon-prime ')] |"
                ".//span[contains(@class, 'sprPrime')]"
            )
            is_prime_pantry = li.xpath(
                "*/descendant::i[contains(concat(' ',@class,' '),'"
                "a-icon-prime-pantry ')]"
            )
            data_asin = self._is_empty(
                li.xpath('@id').extract()
            )

            is_sponsored = bool(li.xpath('.//h5[contains(text(), "ponsored")]').extract())

            try:
                idx = int(self._is_empty(
                    re.findall(r'\d+', data_asin)
                ))
            except ValueError:
                continue

            if idx > last_idx:
                link = self._is_empty(
                    li.xpath(
                        ".//a[contains(@class,'s-access-detail-page')]/@href |"
                        ".//h3[@class='newaps']/a/@href"
                    ).extract()
                )
                if not link:
                    continue

                if 'slredirect' in link:
                    link = 'http://' + self.allowed_domains[0] + '/' + link

                links.append((link, is_prime, is_prime_pantry, is_sponsored))
            else:
                break

            last_idx = idx

        if not links:
            self.log("Found no product links.", WARNING)

        return links

    def _get_sponsored_links(self, response):
        sponsored_links = response.xpath("//a[contains(@class, 's-access-detail-page')]/@href").extract()
        return sponsored_links

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
            item['name'] = prod.xpath("./@title").extract()
            item['url'] = prod.xpath("./@href").extract()
            items.append(item)
        return items

    def _get_ads_path(self):
        return ["//div[@class='acs-shwcs-image-single']//a",
                "//div[@class='acsUxWidget']//div[contains(@class, 'bxc-grid__column--12-of-12')]"
                "//div[contains(@class, 'bxc-grid__image')]//a"]

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        next_link = meta.get('next_link')
        if not next_link:
            next_link = self._parse_next_page_link(response)
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        return next_link

    def _parse_next_page_link(self, response):
        next_page = response.xpath('//span[@class="pagnRA"]/a[@class="pagnNext"]'
                                   '/@href').extract()
        if next_page:
            next_page = urlparse.urljoin(response.url, next_page[0])
            return next_page
