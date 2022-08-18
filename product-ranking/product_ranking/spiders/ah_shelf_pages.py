import re
import json
import urlparse
import traceback

from scrapy import Request
from scrapy.log import WARNING

from .ah import AhProductsSpider

from product_ranking.items import SiteProductItem
from product_ranking.guess_brand import guess_brand_from_first_words


class AhShelfPagesSpider(AhProductsSpider):
    name = 'ah_shelf_urls_products'

    CATEGORY_URL = 'https://www.ah.nl/service/rest/delegate?url={path}'

    ADS_URL = 'https://www.ah.nl/service/rest/delegate?url={path}'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        super(AhShelfPagesSpider, self).__init__(*args, **kwargs)

        self.detect_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_ads = True

    def start_requests(self):
        meta = {'search_term': "", 'remaining': self.quantity}
        path = urlparse.urlparse(self.product_url).path

        request = Request(url=self.CATEGORY_URL.format(path=path),
                          meta=meta)

        if self.detect_ads:
            request = request.replace(callback=self._scrape_ads_links)

        yield request

    def _scrape_product_links(self, response):
        meta = response.meta.copy()
        items = meta.get('items', [])

        if not items and not self.detect_ads:
            items = self._get_items(response)

        ads = meta.get('ads', [])

        for item in items:
            product_info = item.get('_embedded', {}).get('product', {})
            product = self._parse_product(SiteProductItem(), product_info)
            product_url = item.get('navItem', {}).get('link', {}).get('href')
            product['url'] = urlparse.urljoin(response.url, product_url)

            if self.detect_ads and ads:
                product['ads'] = ads
                product['ads_count'] = len(ads)
            yield None, product

    def _scrape_ads_links(self, response):
        try:
            meta = response.meta.copy()
            ads_lanes = []

            for lane in json.loads(response.body)['_embedded']['lanes']:
                if lane['type'] in ('PromoLane', 'RichLane'):
                    ads_lanes.append(lane['_embedded'].get('items', []))

            ads = []

            for items in ads_lanes:
                for item in items:
                     if item.get('_embedded', {}).get('foldOut', {}).get('_links', {}).get('self', {}).get('href'):
                         ads.append({
                                'ad_url': urlparse.urljoin(response.url, item.get('_embedded', {}).get('foldOut', {})
                                                           .get('_links', {}).get('self', {}).get('href')),
                                'ad_image': item.get('image', {}).get('link', {}).get('href'),
                                'ad_dest_products': []
                            })
                     elif item.get('_embedded', {}).get('fallbackItem', {}).get('navItem', {}).get('link', {}).get('href'):
                         ads.append({
                                'ad_url': urlparse.urljoin(response.url, item.get('_embedded', {}).get('fallbackItem', {})
                                                           .get('navItem', {}).get('link', {}).get('href')),
                                'ad_image': item.get('_embedded', {}).get('fallbackItem', {}).get('image')
                                                            .get('link', {}).get('href'),
                                'ad_dest_products': []
                            })

            meta['ads'] = ads
            meta['index'] = 0

            if ads:
                return Request(
                    url=ads[0]['ad_url'],
                    callback=self._scrape_ad_products,
                    meta=meta,
                    dont_filter=True
                )
        except:
            return self.parse(response)

    def _get_items(self, response):
        try:
            lanes = [lane['_embedded'].get('items', [])
                     for lane in json.loads(response.body)['_embedded']['lanes']
                     if lane['type'] == 'ProductLane']
            items = [item for items in lanes for item in items]
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
            items = []

        return [i for i in items if i.get('type') == 'Product']

    def _scrape_ad_products(self, response):
        meta = response.meta.copy()
        ads = meta.get('ads', [])
        index = meta.get('index', 0)

        try:
            lanes = [
                lane.get('_embedded').get('items', [])
                for lane in json.loads(response.body).get('_embedded', {}).get('lanes', [])
                if lane.get('_embedded', {}).get('items', [])
            ]
            products = [
                item for items in lanes for item in items if item.get('type') == 'Product'
            ]
            ads_dest_products = [
                {
                    'url': urlparse.urljoin(response.url, self._get_product_link(product)),
                    'title': self._get_product_title(product),
                    'brand': guess_brand_from_first_words(self._get_product_title(product)),
                    'reseller_id': self._get_reseller_id(self._get_product_link(product))
                }
                for product in products
            ]

            ads[index]['ad_dest_products'] += ads_dest_products
            meta['ads'] = ads
        except:
            self.log('Parsing Ads Json Error: {}'.format(traceback.format_exc()))

        if index + 1 < len(ads):
            index += 1
            meta['index'] = index
            return Request(
                url=ads[index]['ad_url'],
                meta=meta,
                callback=self._scrape_ad_products,
                dont_filter=True
            )
        return self._scrape_ads(ads)

    def _scrape_next_results_page_link(self, response):
        return

    def _scrape_total_matches(self, response):
        return

    @staticmethod
    def _get_product_title(product):
        return product.get('_embedded', {}).get('product', {}).get('description')

    @staticmethod
    def _get_product_link(product):
        return product.get('navItem', {}).get('link', {}).get('href')

    @staticmethod
    def _get_reseller_id(link):
        reseller_id = re.search('product/wi(\d+)', link)
        return reseller_id.group(1) if reseller_id else None

    @staticmethod
    def _scrape_ads(ads):
        prod = SiteProductItem()
        prod['ads'] = ads
        return prod