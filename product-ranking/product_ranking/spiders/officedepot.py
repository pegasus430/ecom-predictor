# -*- coding: utf-8 -*-#
import re
import json
import urllib
import urlparse
import traceback

from scrapy import Request
from scrapy.conf import settings
from HTMLParser import HTMLParser

from product_ranking.items import SiteProductItem, Price, \
    BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.utils import is_empty


class OfficedepotProductsSpider(BaseProductsSpider):
    name = 'officedepot_products'
    allowed_domains = ["officedepot.com", "www.officedepot.com", 'bazaarvoice.com']
    start_urls = []

    SEARCH_URL = "http://www.officedepot.com/mobile/search.do?recordsPerPageNumber=60&" \
                 "Ntt={search_term}&No={offset}&paging=true"

    PRODUCT_URL = "http://www.officedepot.com/mobile/skuPage.do?sku={sku}"

    productsPerPage = 60

    REVIEW_URL = "http://officedepot.ugc.bazaarvoice.com/2563" \
                 "/{product_id}/reviews.djs?format=embeddedhtml"

    VARIANTS_URL = 'http://www.officedepot.com/mobile/getSkuAvailable' \
                   'Options.do?familyDescription={name}&sku={sku}&noLogin=true'

    QA_URL = "http://officedepot.ugc.bazaarvoice.com/answers/2563/product/{product_id}/questions.djs?format=embeddedhtml"

    def __init__(self, *args, **kwargs):

        self.br = BuyerReviewsBazaarApi(called_class=self)
        super(OfficedepotProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                    offset=0
                ),
                meta={
                    'search_term': st,
                    'remaining': self.quantity,
                    'offset': 0
                },
            )

        if self.product_url:
            sku = self._get_product_id(self.product_url)
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.PRODUCT_URL.format(sku=sku),
                          self._parse_single_product,
                          meta={'product': prod})

    def _parse_single_product(self, response):
        return self.parse_product(response)

    @staticmethod
    def _get_product_id(url):
        match = re.search(r'(?<=products/)\d+', url)
        if match:
            return match.group(0)

    def parse_product(self, response):
        try:
            item = json.loads(response.body_as_unicode())
        except:
            self.log("Failed to load product info from JSON response: {}".format(traceback.format_exc()))
        else:
            product = response.meta.get('product', SiteProductItem())

            product['locale'] = 'en_US'

            # Parse title
            title = item.get('catalog', {}).get('shortDescription')
            if not title:
                title = item.get('catalog', {}).get('longDescription')
            if not title:
                title = item.get('seoDescription', '').replace('-', ' ')
            cond_set_value(product, 'title', title)

            # Parse image
            image = item.get('largeImage')
            if image:
                cond_set_value(product, 'image_url',
                               urlparse.urljoin("http://s7d1.scene7.com/is/image/officedepot/", image))

            # Parse brand
            brand = [x.get('value') for x in item.get('attributes', {}).get('pairs', []) if
                     x.get('name') == 'brand name']
            cond_set_value(product, 'brand', brand[0] if brand else guess_brand_from_first_words(title))

            # Parse sku
            cond_set_value(product, 'sku', item.get('sku'))

            # Parse url
            product['url'] = urlparse.urljoin(response.url, item.get('seoFriendlyLink', ''))

            # Parse price
            price = self.parse_price(item.get('price'))
            cond_set_value(product, 'price', Price(price=float(price), priceCurrency='USD') if price else None)

            # Parse was_now
            was_now = self._parse_was_now(response)
            cond_set_value(product, 'was_now', was_now)

            # Parse save amount
            buy_save_amount = self._parse_buy_save_amount(response)
            cond_set_value(product, 'buy_save_amount', buy_save_amount)

            # Parse promotions
            cond_set_value(product, 'promotions', any([was_now, buy_save_amount]))

            # Parse reseller_id
            reseller_id = [x.get('value') for x in item.get('attributes', {}).get('pairs', []) if x and
                           x.get('name') == 'Manufacturer #']
            cond_set_value(product, "reseller_id", reseller_id[0] if reseller_id else None)

            # Parse is out of stock
            cond_set_value(product, 'is_out_of_stock', item.get('availability', {}).get('outOfStock'))

            # Parse in-store pickup
            cond_set_value(product, 'in_store_pickup', item.get('availability', {}).get('pickup'))

            # Parse categories and department
            categories = item.get('skuCategoryInfo', {}).values()
            cond_set_value(product, 'categories', categories)
            if categories:
                cond_set_value(product, 'department', categories[-1])

            response.meta['product'] = product
            name = HTMLParser().unescape(product.get('title', '')).encode("utf-8")
            sku = product.get('sku')
            if name and sku:
                name = name.split(',')[0]
                return Request(self.VARIANTS_URL.format(name=name,
                                                        sku=sku),
                               callback=self._parse_variants,
                               meta=response.meta,
                               dont_filter=True)

    def parse_price(self, price):
        try:
            if str(price).startswith('$'):
                price = price[1:]
            return float(price.replace(',', ''))
        except:
            self.log("Failed to parse price: {}".format(traceback.format_exc()))

    def _parse_was_now(self, response):
        try:
            data = json.loads(response.body)
            current_price = self.parse_price(data.get('price'))
            old_price = self.parse_price(data.get('priceWithTax'))
            if all([current_price, old_price]):
                return ', '.join([str(current_price), str(old_price)])
        except:
            self.log("Failed to parse json info: {}".format(traceback.format_exc()))

    def _parse_buy_save_amount(self, response):
        try:
            data = json.loads(response.body)
            save_amount = data.get('rebateList', {}).get('totalRebatesAmt')
            return save_amount if save_amount else None
        except:
            self.log("Failed to parse json info: {}".format(traceback.format_exc()))

    def _parse_variants(self, response):
        product = response.meta['product']
        try:
            data = json.loads(response.body)
            variants = []

            if data.get('success'):
                for sku in data.get('skus', []):
                    vr = {}
                    vr['url'] = urlparse.urljoin(response.url, sku.get('url'))
                    vr['skuId'] = sku.get('sku')
                    price = is_empty(re.findall(
                        '\$([\d\.]+)', sku.get('attributesDescription', '')))
                    if price:
                        vr['price'] = price

                    name = sku.get('description', '')
                    if name:
                        vr['properties'] = {'title': name}

                    vr['image_url'] = sku.get('thumbnailImageUrl').split('?')[0]
                    variants.append(vr)

                product['variants'] = variants

            return Request(self.REVIEW_URL.format(name=product['title'],
                                                  product_id=product['sku']),
                           callback=self.parse_buyer_reviews,
                           meta=response.meta,
                           )
        except:
            self.log("Failed to parse variants info: {}".format(traceback.format_exc()))

        return product

    def parse_buyer_reviews(self, response):
        buyer_reviews_per_page = self.br.parse_buyer_reviews_per_page(response)

        product = response.meta['product']
        product['buyer_reviews'] = BuyerReviews(**buyer_reviews_per_page)

        return product

    def _scrape_total_matches(self, response):
        return response.meta['body'].get('totalRecords')

    def _get_products(self, response):
        try:
            body = json.loads(response.body_as_unicode())
            response.meta['body'] = body
        except:
            response.meta['body'] = {}
        for req_or_prod in super(OfficedepotProductsSpider, self)._get_products(response):
            yield req_or_prod

    def _scrape_product_links(self, response):
        links = [self.PRODUCT_URL.format(sku=sku) for sku in
                 [sku.get('sku') for sku in response.meta['body'].get('skus', [])]]
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        total = self._scrape_total_matches(response)
        response.meta['offset'] += 1
        offset = self.productsPerPage * response.meta['offset']
        if offset < total:
            return Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=response.meta['search_term'],
                    offset=offset),
                meta=response.meta)
