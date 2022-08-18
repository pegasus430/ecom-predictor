# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import json
import re
import traceback
import urlparse
import urllib

from scrapy.log import WARNING
from scrapy.http import Request

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults


class AhProductsSpider(BaseProductsSpider):
    name = 'ah_products'
    allowed_domains = ["ah.nl"]

    SEARCH_URL = 'https://www.ah.nl/service/rest/delegate?url=' \
                 '/zoeken?rq={search_term}&sorting={sort}'

    ADS_URL = 'https://securepubads.g.doubleclick.net/gampad/ads?gdfp_req=1&' \
              'output=json_html&callback=googletag.impl.pubads.callbackProxy1&' \
              'impl=fifs&json_a=1&eid=21060970%2C108809103%2C21060361&sc=1&sfv=1-0-13&' \
              'iu_parts=46888723%2Cah.nl%2Czoeken&' \
              'enc_prev_ius=%2F0%2F1%2F2&prev_iu_szs=2x1&' \
              'prev_scp=um%3D3%26om%3D0%26ct%3Du%26tst%3D0%26pos%3D1%26rq%3D{search_term}%26ksg%3Dr3wrxc70k%2Cr6yyc747d%26kuid%3Dr2h259abx&' \
              'cookie=ID%3Deda981633a646872%3AT%3D1502731619%3AS%3DALNI_Mbe02UDTN-lHwSGfaBhejE9JlzTsw&abxe=1'

    REST_PROD_URL = 'https://www.ah.nl/service/rest/delegate?url=/producten/' \
                    'product/{product_id}/{product_name}'

    REGEXP_PROD_URL = re.compile('^(https?://)?(www.)?ah.nl/(producten/'
                                 'product/(?P<product_id>[^/]+)/'
                                 '(?P<product_name>[^/]+)/?)')

    SORT_BY = {
        'relevance': 'relevance',
        'name': 'name_asc',
    }

    PRICE_CURRENCY = 'EUR'

    def __init__(self, *args, **kwargs):
        self.sort_by = self.SORT_BY.get(
            kwargs.get('order', 'relevance'), 'relevance')
        formatter = FormatterWithDefaults(sort=self.sort_by)
        super(AhProductsSpider, self).__init__(formatter, *args, **kwargs)

        self.detect_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_ads = True

    def start_requests(self):
        for st in self.searchterms:
            request = Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                ),
                meta={'search_term': st, 'remaining': self.quantity},
            )

            if self.detect_ads:
                request = request.replace(url=self.ADS_URL.format(search_term=urllib.quote_plus(st.encode('utf-8'))),
                                          callback=self._get_ads_product)
            yield request

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod})

    def _parse_single_product(self, response):
        product = self.REGEXP_PROD_URL.search(response.url)
        if not product:
            self.log('Cannot parse product url.', WARNING)
            return

        yield Request(
            self.REST_PROD_URL.format(**product.groupdict()),
            callback=self.parse_single_product,
            meta={'product': response.meta['product']}
        )

    def parse_single_product(self, response):
        product = response.meta['product']
        try:
            product_info = next(
                    lane['_embedded']['items'][0]['_embedded']['product']
                    for lane in json.loads(response.body)['_embedded']['lanes']
                    if lane['type'] == 'ProductDetailLane'
            )
            product_sku = next(
                    lane['_embedded']['items'][0]['value']
                    for lane in json.loads(response.body)['_embedded']['lanes']
                    if lane['type'] == 'Lane'
            )
            product_info['sku'] = product_sku
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
            product['not_found'] = True
            return product

        return self._parse_product(product, product_info)

    def _parse_product(self, product, product_info):
        product['locale'] = 'nl_NL'
        sku = unicode(product_info.get('sku', ''))
        product['sku'] = sku
        product['reseller_id'] = sku

        title = product_info.get('description')
        unit_size = product_info.get('unitSize')
        product['title'] = title.replace(u'\xad', '') + ', ' + unit_size

        brand = product_info.get('brandName')
        if not brand and title:
            brand = guess_brand_from_first_words(title)
        product['brand'] = brand

        product['is_out_of_stock'] = not product_info.get('availability', {}).get('orderable')
        categories = product_info.get('categoryName', '').split('/')
        if categories:
            product['categories'] = categories
            product['department'] = categories[-1]

        product['price'] = Price(
            priceCurrency=self.PRICE_CURRENCY,
            price=product_info.get('priceLabel', {}).get('now', 0)
        )

        unitofusesize = product_info.get('details', {}).get('unitOfUseSize')
        if unitofusesize:
            product['price_per_volume'] = (re.sub('[^0-9,]', "", unitofusesize)).replace(',', '.')
            volume_measure = unitofusesize.split('per')[-1]
            product['volume_measure'] = volume_measure.split(' ')[1] if volume_measure else None

        product['promotions'] = product_info.get('discount', {}).get('type', {}).get('name') == 'BONUS'

        images = product_info.get('images', [{}])
        image = max(images, key=lambda x: x.get('height'))
        product['image_url'] = image.get('link', {}).get('href')

        price_info = product_info.get('priceLabel', {})
        if price_info.get('was'):
            product['was_now'] = "{}, {}".format(price_info.get('now'), price_info.get('was'))

        discount_label = product_info.get('discount', {}).get('label', '')
        fm = re.match(r"(\d+) voor (\d*\.\d+|\d+)", discount_label)
        if fm:
            product['buy_for'] = "{}, {}".format(fm.group(1), fm.group(2))

        if 'gratis' in discount_label:
            gm = re.findall(r'\d+', discount_label)
            try:
                product['buy_getfree'] = "{}, {}".format(gm[0], gm[1])
            except:
                self.log('Error Parsing Free: {}'.format(traceback.format_exc()))

        sm = re.match(r"(\d*\.\d+|\d+)% korting", discount_label)
        if sm:
            product['save_percent'] = "{}".format(sm.group(1))

        return product

    def _get_ads_product(self, response):
        meta = response.meta.copy()

        image_urls = []
        images = re.findall('https://tpc.googlesyndication.com/pagead/imgad\?id(.*?)x22', response.body)
        for image in images:
            image_urls.append('https://tpc.googlesyndication.com/pagead/imgad?id='
                              + image.replace('\\x3d', '').replace('\\', ''))

        ads_urls = []
        ads_api_urls = []
        urls = re.findall('https://www.ah.nl/zoeken(.*?)x22', response.body)
        for url in urls:
            ads_urls.append('https://www.ah.nl/zoeken' + url.replace('\\x3d', '=').replace('\\', ''))
            ads_api_urls.append('https://www.ah.nl/service/rest/delegate?url=/zoeken'
                                + url.replace('\\x3d', '=').replace('\\', ''))

        ads = []
        for i, url in enumerate(ads_urls):
            ad = {
                'ad_url': url,
                'ad_image': image_urls[i]
            }
            ads.append(ad)

        if ads_urls:
            meta['ads_idx'] = 0
            meta['image_urls'] = image_urls
            meta['ads_urls'] = ads_urls
            meta['ads_api_urls'] = ads_api_urls
            meta['ads'] = ads

            return Request(
                url=ads_api_urls[0],
                meta=meta,
                callback=self._parse_ads_product,
                dont_filter=True,
            )
        else:
            return Request(
                url=self.SEARCH_URL.format(search_term=response.meta.get('search_term'),
                                           sort=self.SORT_BY['relevance']).replace('\\xad', ''),
                callback=self._get_ads_category,
                meta=response.meta,
                dont_filter=True,
            )

    def _get_ads_category(self, response):
        meta = response.meta.copy()

        ads_urls = []
        ads_api_urls = []
        image_urls = []

        try:
            content = json.loads(response.body_as_unicode())
            if content:
                content = content.get('_embedded').get('lanes')[-2].get('_embedded').get('items')
                for data in content:
                    link = data.get('navItem', {}).get('link', {}).get('href', {})
                    if link and 'producten/product' not in link:
                        ads_urls.append('https://www.ah.nl' + link)
                        ads_api_urls.append('https://www.ah.nl/service/rest/delegate?url=' + link)
                        image_urls.append(data.get('image').get('link').get('href'))
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)

        ads = []
        for i, url in enumerate(ads_urls):
            ad = {
                'ad_url': url,
                'ad_image': image_urls[i]
            }
            ads.append(ad)

        if ads_urls:
            meta['ads_idx'] = 0
            meta['image_urls'] = image_urls
            meta['ads_urls'] = ads_urls
            meta['ads_api_urls'] = ads_api_urls
            meta['ads'] = ads

            return Request(
                url=ads_api_urls[0],
                meta=meta,
                callback=self._parse_ads_product,
                dont_filter=True,
            )
        else:
            return Request(
                url=self.SEARCH_URL.format(search_term=response.meta.get('search_term'),
                                           sort=self.SORT_BY['relevance']).replace('\\xad', ''),
                meta=response.meta,
            )

    def _parse_ads_product(self, response):
        ads = response.meta.get('ads', [])
        ads_idx = response.meta.get('ads_idx')
        ads_api_urls = response.meta.get('ads_api_urls')

        products_info = self._get_products_info(response)
        if products_info:
            products = [
                {
                    'url': item['url'],
                    'name': item['name'],
                    'brand': item['brand'],
                    'reseller_id': item['reseller_id'],
                } for item in products_info
            ]

            ads[ads_idx]['ad_dest_products'] = products
        response.meta['ads'] = ads

        ads_idx += 1
        if ads_idx < len(ads_api_urls):
            link = ads_api_urls[ads_idx]
            response.meta['ads_idx'] += 1
        else:
            return Request(
                url=self.SEARCH_URL.format(search_term=response.meta.get('search_term'),
                                           sort=self.SORT_BY['relevance']).replace('\\xad', ''),
                meta=response.meta
            )

        return Request(
            url=link,
            meta=response.meta,
            callback=self._parse_ads_product,
            dont_filter=True
        )

    def _get_products_info(self, response):
        items = []
        try:
            content_list = json.loads(response.body_as_unicode())
            content_list = content_list.get('_embedded').get('lanes')
            for content in content_list:
                data_list = content.get('_embedded').get('items')
                for data in data_list:
                    item = {}
                    item['name'] = data.get('_embedded', {}).get('product', {}).get('description')
                    item['brand'] = data.get('_embedded', {}).get('product', {}).get('brandName')
                    href = data.get('navItem', {}).get('link', {}).get('href')
                    if href:
                        item['url'] = 'https://www.ah.nl' + href
                    item['reseller_id'] = data.get('_embedded', {}).get('product', {}).get('id')

                    if item['name'] and item['reseller_id']:
                        item['name'] = item['name'].replace('-', '')
                        items.append(item)
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)

        return items

    def _scrape_product_links(self, response):
        meta = response.meta.copy()
        try:
            items = next(lane['_embedded'].get('items', []) for lane
                    in json.loads(response.body)['_embedded']['lanes']
                    if lane['type'] == 'SearchLane')
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
            items = []

        for item in [i for i in items if i.get('type') == 'Product']:
            product_info = item.get('_embedded', {}).get('product', {})
            product = self._parse_product(SiteProductItem(), product_info)
            product_url = item.get('navItem', {}).get('link', {}).get('href')
            product['url'] = urlparse.urljoin(response.url, product_url)
            if self.detect_ads:
                product['ads'] = meta.get('ads')
            yield None, product

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        try:
            next_url = next(lane['navItem']['link']['href'] for lane
                            in json.loads(response.body)['_embedded']['lanes']
                            if lane['type'] == 'LoadMoreLane')
            return Request(url=urlparse.urljoin(response.url, next_url), meta=meta)
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)

    def _scrape_total_matches(self, response):
        try:
            total_matches = int(json.loads(response.body)['_meta']
                ['analytics']['parameters']['ns_search_result'])
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
            total_matches = 0

        return total_matches
