# -*- coding: utf-8 -*-

import re
import sys
import urlparse

from urlparse import urljoin

from lxml import html
from scrapy import Request
from product_ranking.items import SiteProductItem

from product_ranking.spiders.tesco import TescoProductsSpider


class TescoShelfPagesSpider(TescoProductsSpider):
    name = 'tesco_shelf_urls_products'
    allowed_domains = ["tesco.com", "doubleclick.net"]

    headers = {
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.98 Safari/537.36"
    }

    ads_api_url = "https://securepubads.g.doubleclick.net/gampad/ads?gdfp_req=1&correlator=679297608344486" \
                  "&output=json_html&callback=googletag.impl.pubads.callbackProxy1&impl=fifs&json_a=1&eid=108809133%2C108809107%2C108809155&sc=1" \
                  "&sfv=1-0-13&iu_parts=8326%2Cgrocery%2C{iu_part}&enc_prev_ius=%2F0%2F1%2F2%2F3" \
                  "&prev_iu_szs=320x50%7C300x250%7C375x258%7C375x110&fluid=height&cust_params=shelf%3D{department}%26nocid%3Dyes%26store%3D%26tppid%3D" \
                  "&cookie=ID%3Ddd725205b84ae8f2%3AT%3D1508995246%3AS%3DALNI_MaczjUTuXSojhHBfP5tEpIsRCncLg&cdm=www.tesco.com&lmt=1508416477&dt=1508999166937" \
                  "&ea=0&frm=23&biw=763&bih=810&isw=527&ish=0&oid=3&adxs=18&adys=191&adks=1288992070&gut=v2&ifi=1&ifk=2311946005" \
                  "&u_tz=120&u_his=5&u_h=900&u_w=1440&u_ah=876&u_aw=1375&u_cd=24&u_nplug=4&u_nmime=5&u_sd=1&flash=0&nhd=1&iag=3" \
                  "&url=https%3A%2F%2Fwww.tesco.com%2Fgroceries%2Fdfp%2Fdfp-beaa1a3b14.html" \
                  "&ref={product_url}"

    def _setup_class_compatibility(self):
        """ Needed to maintain compatibility with the SC spiders baseclass """
        self.quantity = sys.maxint
        self.site_name = self.allowed_domains[0]
        self.user_agent_key = None
        self.current_page = 1

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': sys.maxint, 'search_term': ''}.copy()

    def __init__(self, *args, **kwargs):
        self.product_url = kwargs['product_url']
        kwargs.pop('quantity', None)
        self._setup_class_compatibility()

        self.num_pages = int(kwargs.pop('num_pages', 1))
        self.detect_shelf_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_shelf_ads = True

        # variants are switched off by default, see Bugzilla 3982#c11
        self.scrape_variants_with_extra_requests = False
        if 'scrape_variants_with_extra_requests' in kwargs:
            scrape_variants_with_extra_requests = kwargs['scrape_variants_with_extra_requests']
            if scrape_variants_with_extra_requests in (1, '1', 'true', 'True', True):
                self.scrape_variants_with_extra_requests = True

        super(TescoShelfPagesSpider, self).__init__(site_name=self.site_name, *args, **kwargs)

    def start_requests(self):
        request = Request(url=self.product_url,
                          meta=self._setup_meta_compatibility(),
                          dont_filter=True)

        if self.detect_shelf_ads:
            request = request.replace(callback=self._start_ads)
        yield request

    @staticmethod
    def valid_url(url):
        if not re.findall("http(s){0,1}\:\/\/", url):
            url = "http://" + url
        return url

    def _scrape_product_links(self, response):
        meta = response.meta.copy()
        st = meta.get('search_term')

        items = self._get_product_links(response)
        if items:
            for item in items:
                prod_item = SiteProductItem()
                if self.detect_shelf_ads is True:
                    prod_item['ads'] = meta.get('ads')

                req = Request(
                    url=urlparse.urljoin(response.url, item),
                    callback=self.parse_product,
                    meta={
                        "product": prod_item,
                        'search_term': st,
                        'remaining': self.quantity,
                    },
                    dont_filter=True
                )
                yield req, prod_item

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        current_page = meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return
        self.current_page += 1

        next_link = self._parse_next_page_link(response)
        return next_link

    @staticmethod
    def _get_product_links(response):
        links = []
        items = response.xpath(
            '//div[contains(@class,"productLists")]'
            '//ul[contains(@class,"products grid")]'
            '/li[contains(@class,"product")]//h2/a/@href | '
            '//a[contains(@class, "product-tile--title")]/@href'
        ).extract()
        for item in items:
            links.append(urlparse.urljoin(response.url, item))
        return links

    @staticmethod
    def _get_ads_product_links(response):
        links = []
        items = response.xpath('//div[@class="product-details--content"]/a[1]/@href').extract()
        for item in items:
            links.append(urlparse.urljoin(response.url, item))
        return links

    def _get_ads_product_names(self, response):
        item_names = []
        items = response.xpath('//div[@class="product-details--content"]/a[1]/text()').extract()
        for item in items:
            item_names.append(self._clean_text(item))
        return item_names

    def _start_ads(self, response):
        meta = response.meta.copy()
        csrf = response.xpath("//input[@name='_csrf']/@value").extract()
        iu_part = None,
        department = None
        shelf_params = re.search('shop/(.*)', self.product_url)
        if shelf_params:
            shelf_params = shelf_params.group(1).rsplit('/', 1)
            if shelf_params:
                iu_part = shelf_params[0]
                department = shelf_params[-1]
        if iu_part and department and csrf:
            meta['_csrf'] = csrf[0]
            return Request(
                url=self.ads_api_url.format(
                    product_url=self.product_url,
                    iu_part=iu_part.replace('/', '%2C'),
                    department=department
                ),
                callback=self._get_ads_product,
                meta=meta
            )

    def _get_ads_product(self, response):
        meta = response.meta.copy()
        csrf = meta.get('_csrf')
        ads_html_content = None
        ads_content = self._find_between(response.body.decode('string_escape'), '"_html_":', ',"_snippet_"')
        if ads_content:
            ads_html_content = html.fromstring(ads_content)

        ads = []
        ads_urls = []
        image_urls = []
        if ads_html_content is not None:
            ads_urls.extend([ad for ad in ads_html_content.xpath('//a/@href | //a[contains(@class, "stamp--")]/@href')])
            image_urls.extend([ad for ad in ads_html_content.xpath(
                '//a//img/@src | //a[contains(@class, "stamp--")]/span[contains(@class, "img--container")]/img[1]/@src')])
        for i, url in enumerate(ads_urls):
            ad = {
                'ad_url': url,
                'ad_image': image_urls[i]
            }
            ads.append(ad)

        if ads_urls:
            meta['ads_idx'] = 0
            meta['image_urls'] = image_urls
            meta['ads'] = ads
            meta['ads_urls'] = ads_urls
            return Request(
                url=ads_urls[0],
                meta=meta,
                headers=self.headers,
                cookies={'_csrf': csrf},
                callback=self._parse_ads_product,
                dont_filter=True,
            )
        else:
            return Request(
                url=self.product_url,
                callback=self._parse_shelf_product,
                meta=response.meta
            )

    def _parse_ads_product(self, response):
        ads = response.meta.get('ads', [])
        ads_idx = response.meta.get('ads_idx')
        ads_urls = response.meta.get('ads_urls')

        product_links = self._get_ads_product_links(response)
        product_names = self._get_ads_product_names(response)
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
            return Request(
                url=self.product_url,
                callback=self._parse_shelf_product,
                meta=response.meta
            )

        return Request(
            url=link,
            meta=response.meta,
            callback=self._parse_ads_product,
            dont_filter=True
        )

    def _parse_shelf_product(self, response):
        return self.parse(response)

    @staticmethod
    def _find_between(s, first, last, offset=0):
        try:
            s = s.decode("utf-8")
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()
