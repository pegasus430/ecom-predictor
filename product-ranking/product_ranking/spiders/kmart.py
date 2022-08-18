from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback
import urllib

from scrapy.http import Request
from scrapy.log import WARNING

from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator


class KmartProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'kmart_products'
    allowed_domains = ["www.kmart.com"]

    SEARCH_URL = "http://www.kmart.com/service/search/v2/productSearch?catalogId=10104&keyword={search_term}" \
                 "&pageNum={page_num}&rmMattressBundle=true&searchBy=keyword&storeId=10151&tabClicked=All" \
                 "&unitNo=null&visitorId=Test&zip=90017"

    ITEM_URL = "http://www.kmart.com/content/pdp/config/products/v1/products/{}?site=kmart"

    REVIEW_URL = "http://www.kmart.com/content/pdp/ratings/single/search/Kmart/{}&targetType=product&limit=10&offset=0"

    PRICE_URL = "http://www.kmart.com/content/pdp/products/pricing/v2/get/price/display/json?ssin={}" \
                "&priceMatch=Y&memberType=G&urgencyDeal=Y&site=KMART"

    HEADERS = {
        'Host': 'www.kmart.com',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)',
        'AuthID': 'aA0NvvAIrVJY0vXTc99mQQ==',
    }

    def start_requests(self):
        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                    page_num=1,
                ),
                meta={'search_term': st, 'remaining': self.quantity, 'current_page': 1},
                headers=self.HEADERS
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''

            prod_id = re.findall(r'\/p-([^/?]*)', self.product_url)
            self.HEADERS.setdefault('Referer', self.product_url)

            if prod_id:
                yield Request(self.ITEM_URL.format(prod_id[0]),
                              self._parse_single_product,
                              headers=self.HEADERS,
                              meta={'product': prod})

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        try:
            data = json.loads(response.body)['data']['product']
        except:
            self.log('Invalid Product JSON: {}'.format(traceback.format_exc()), WARNING)
            return product

        reseller_id = data.get('id')
        cond_set_value(product, 'reseller_id', reseller_id)

        title = data.get('name')
        cond_set_value(product, 'title', title)

        brand = data.get('brand', {}).get('name')
        cond_set_value(product, 'brand', brand)

        model = data.get('mfr', {}).get('modelNo')
        cond_set_value(product, 'model', model)

        image_url = self._parse_image(data)
        cond_set_value(product, 'image_url', image_url)

        product['locale'] = "en-US"

        if reseller_id:
            return Request(
                self.PRICE_URL.format(reseller_id),
                callback=self._parse_price,
                headers=self.HEADERS,
                meta={'product': product}
            )

        return product

    def _parse_price(self, response):
        product = response.meta.get('product', SiteProductItem())
        try:
            data = json.loads(response.body)['priceDisplay']['response'][0]
        except:
            self.log('Invalid Price JSON: {}'.format(traceback.format_exc()), WARNING)
            return product

        price = data.get('prices', {}).get('finalPrice', {}).get('min')
        if price:
            product['price'] = Price(price=price, priceCurrency='USD')

        return product

    def _parse_image(self, data):
        image_url = None
        assets = data.get('assets', {}).get('imgs')
        if assets:
            assets = assets[0]
            image_url = assets.get('vals')[0].get('src') if assets.get('vals') else None

        if image_url:
            return image_url

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body)['data']
        except:
            self.log('Invalid Products JSON: {}'.format(traceback.format_exc()), WARNING)

        return data.get('productCount') if data else None

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body)['data']
        except:
            self.log('Invalid Products JSON: {}'.format(traceback.format_exc()), WARNING)

        meta = response.meta.copy()
        prod_item = SiteProductItem()
        st = meta.get('search_term')

        if data:
            items = data.get('products', [])
            for item in items:
                item_id = item.get('sin')
                if item_id:
                    item_req = Request(
                        self.ITEM_URL.format(item_id),
                        callback=self.parse_product,
                        headers=self.HEADERS,
                        meta={
                            "product": prod_item,
                            'search_term': st,
                            'remaining': self.quantity,
                        }
                    )

                    yield item_req, prod_item

    def _scrape_next_results_page_link(self, response):
        data = None
        try:
            data = json.loads(response.body)['data']
        except:
            self.log('Invalid Products JSON: {}'.format(traceback.format_exc()), WARNING)

        if not data:
            return

        meta = response.meta.copy()
        st = meta.get('search_term')
        current_page = meta.get('current_page')

        total = data.get('productCount')
        offset = data.get('pageEnd')

        if total and offset >= total:
            return

        current_page += 1
        meta['current_page'] = current_page
        next_page_link = self.SEARCH_URL.format(page_num=current_page, search_term=st)

        return Request(
            next_page_link,
            meta=meta,
            headers=self.HEADERS
        )
