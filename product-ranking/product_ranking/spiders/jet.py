# -*- coding: utf-8 -*-#

import json
import re
import traceback
import unicodedata

from scrapy.conf import settings
from scrapy.http import Request
from scrapy.log import WARNING

from product_ranking.guess_brand_jet import guess_brand_from_first_words, brand_in_list
from product_ranking.items import Price, SiteProductItem
from product_ranking.powerreviews import parse_powerreviews_buyer_reviews
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty, catch_json_exceptions
from product_ranking.validation import BaseValidator
from spiders_shared_code.jet_variants import JetVariants


class JetProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'jet_products'
    allowed_domains = ['jet.com', 'powerreviews.com']

    SEARCH_URL = "https://jet.com/api/search/"

    PROD_URL = "https://jet.com/api/product/v2"

    START_URL = "https://jet.com/"

    PRICE_URL = "https://jet.com/api/productAndPrice"

    REVIEWS_URL = 'http://readservices-b2c.powerreviews.com/m/786803/l/en_US/product/{sku}/reviews?apikey={api_key}'

    handle_httpstatus_list = [503]

    SORT_MODES = {
        "relevance": "relevance",
        "pricelh": "price_low_to_high",
        "pricehl": "price_high_to_low",
        "member_savings": "smart_cart_bonus"
    }

    def __init__(self, sort_mode=None, *args, **kwargs):
        super(JetProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args, **kwargs)
        self.sort = self.SORT_MODES.get(
            sort_mode) or self.SORT_MODES.get("relevance")
        self.current_page = 1
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36" \
                          " (KHTML, like Gecko) Chrome/66.0.3359.139 Safari/537.36"
        RETRY_HTTP_CODES = settings.get('RETRY_HTTP_CODES')
        if 503 in RETRY_HTTP_CODES:
            RETRY_HTTP_CODES.remove(503)
        settings.overrides['RETRY_HTTP_CODES'] = RETRY_HTTP_CODES
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        settings.overrides['DEFAULT_REQUEST_HEADERS'] = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'x-forwarded-for': '172.0.0.1'
            }
        pipelines = settings.get('ITEM_PIPELINES')
        pipelines['product_ranking.pipelines.SetMarketplaceSellerType'] = None
        settings.set('ITEM_PIPELINES', pipelines)
        self.zip = kwargs.get('zip', '94117')

    def start_requests(self):
        for request in super(JetProductsSpider, self).start_requests():
            request = request.replace(url=self.START_URL,
                                      callback=self.start_requests_with_csrf,
                                      dont_filter=True)
            yield request

    def start_requests_with_csrf(self, response):
        csrf = self.get_csrf(response)
        api_key = self._get_api_key(response)
        st = response.meta.get('search_term')
        st = st.encode('utf-8') if st else st
        prod = SiteProductItem()

        meta = {"product": prod, 'search_term': st,
                'remaining': self.quantity, 'csrf': csrf}

        if not self.product_url:
            yield Request(
                url=self.SEARCH_URL,
                method="POST",
                body=json.dumps({"term": st, "origination": "PLP", "sort": self.sort, "zipcode": self.zip}),
                meta={
                    'search_term': st,
                    'remaining': self.quantity,
                    'csrf': csrf,
                    'api_key': api_key
                },
                dont_filter=True,
                headers={
                    "content-type": "application/json", "x-csrf-token": csrf,
                    "X-Requested-With": "XMLHttpRequest",
                    "jet-referer": "/search?term={}".format(st)
                },
            )
        elif self.product_url:
            prod_id = self.product_url.split('/')[-1]
            prod_id = prod_id.replace("#", "") if prod_id else None
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            meta['handle_httpstatus_list'] = self.handle_httpstatus_list + [410]
            meta['api_key'] = api_key
            yield Request(
                url=self.PROD_URL,
                callback=self._parse_single_product,
                method="POST",
                body=json.dumps({"sku": prod_id, "origination": "none"}),
                meta=meta,
                dont_filter=True,
                headers={
                    "content-type": "application/json", "x-csrf-token": csrf,
                    "X-Requested-With": "XMLHttpRequest",
                    "jet-referer": "/search?term={}".format(st)
                },
            )
        elif self.products_url:
            urls = self.products_url.split('||||')
            for url in urls:
                prod_id = url.split('/')[-1]
                prod['url'] = self.product_url
                prod['search_term'] = ''
                yield Request(
                    url=self.PROD_URL,
                    callback=self._parse_single_product,
                    method="POST",
                    body=json.dumps({"sku": prod_id, "origination": "none"}),
                    meta=meta,
                    dont_filter=True,
                    headers={
                        "content-type": "application/json", "x-csrf-token": csrf,
                        "X-Requested-With": "XMLHttpRequest",
                        "jet-referer": "/search?term={}".format(st)
                    },
                )

    @catch_json_exceptions
    def _parse_product_data(self, response):
        return json.loads(response.body).get('result')

    def parse_product(self, response):
        csrf = response.meta.get('csrf')
        api_key = response.meta.get('api_key')
        search_term = response.meta['search_term']
        product = response.meta['product']

        if response.status == 410:
            product['not_found'] = True
            return product

        reqs = []
        prod_data = self._parse_product_data(response)
        if not prod_data:
            cond_set_value(product, "not_found", True)
            if not product.get('url'):
                cond_set_value(product, "url", self.product_url)
            return product

        title = prod_data.get('title')
        cond_set_value(product, "title", title)

        cond_set_value(product, "reseller_id", prod_data.get('retailSkuId'))
        cond_set_value(product, "model", prod_data.get('part_no'))
        cond_set_value(product, "upc", prod_data.get('upc'))

        desc = prod_data.get('description', "") + "\n" + "\n".join(prod_data.get('bullets', []))
        cond_set_value(product, "description", desc)

        sku = prod_data.get('sku')
        cond_set_value(product, "sku", sku)
        cond_set_value(product, "secondary_id", sku)

        categories = prod_data.get('categoryPath', '').split('|')
        if any(categories):
            cond_set_value(product, 'categories', categories)
            cond_set_value(product, 'department', categories[-1])

        # Construct product url
        prod_id = prod_data.get('retailSkuId')
        prod_name = product.get('title')
        prod_slug = self.slugify(prod_name)
        prod_url = "https://jet.com/product/{}/{}".format(prod_slug, prod_id)
        product["url"] = prod_url

        image_url = prod_data.get('images')
        image_url = image_url[0].get('raw') if image_url else None
        cond_set_value(product, "image_url", image_url)

        cond_set_value(product, "locale", "en_US")

        price_data = prod_data.get('productPrice', {})
        if price_data.get('shippingPromise') == "TwoDay":
            product["deliver_in"] = "2 Days"

        is_out_of_stock = bool(price_data.get('status'))
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        price = price_data.get("referencePrice")
        if price:
            cond_set_value(product, "price", Price(priceCurrency="USD", price=price))

        was_now = None
        was = price_data.get('listPrice')
        if was is not 0:
            was_now = str(price) + ', ' + str(was)
            cond_set_value(product, 'was_now', was_now)

        volume_measure = prod_data.get('typeOfUnitForPricePerUnit')
        cond_set_value(product, 'volume_measure', volume_measure)
        if volume_measure:
            price_per_volume = price_data.get('pricePerUnit')
            cond_set_value(product, 'price_per_volume', price_per_volume)

        if any([was_now, volume_measure]):
            product['promotions'] = True
        else:
            product['promotions'] = False

        brand = guess_brand_from_first_words(title, max_words=8)
        cond_set_value(product, "brand", brand)

        primary_seller = prod_data.get("manufacturer", "").replace(u"®", "").replace(u"™", "")

        seller_type = "marketplace"
        if primary_seller and primary_seller.lower() in title.lower() and brand_in_list(primary_seller):
            seller_type = "site"
            if not brand:
                cond_set_value(product, "brand", primary_seller)


        marketplace = [
            {
                "currency": "USD",
                "price": price,
                "name": primary_seller,
                "price_details_in_cart": False,
                "seller_type": seller_type
            }]
        cond_set_value(product, "marketplace", marketplace)

        JV = JetVariants()
        JV.setupSC(response)
        product["variants"] = JV._variants()

        # Filling other variants prices
        if self.scrape_variants_with_extra_requests:
            for variant in product.get("variants") or []:
                # Default variant already have price filled
                if not variant.get("selected"):
                    # Construct additional requests to get prices for variants
                    prod_id = variant.get("sku")
                    req = Request(
                        url=self.PROD_URL,
                        callback=self.parse_variant_price,
                        method="POST",
                        body=json.dumps({"sku": prod_id, "origination": "none"}),
                        meta={
                            'csrf': csrf,
                            "product": product
                        },
                        dont_filter=True,
                        headers={
                            "content-type": "application/json",
                            "x-csrf-token": csrf,
                            "X-Requested-With": "XMLHttpRequest",
                            "jet-referer": "/search?term={}".format(search_term),
                        },
                    )
                    reqs.append(req)
        if sku and api_key:
            req = Request(
                url=self.REVIEWS_URL.format(
                    sku=sku.lower(), # api can't handle uppercase sku
                    api_key=api_key
                ),
                callback=self.parse_buyer_reviews,
                meta={'product': product},
                dont_filter=True
            )
            reqs.append(req)

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    @staticmethod
    def _get_api_key(response):
        api_key = re.search(r'&quot;apiKey&quot;:&quot;(.*?)&quot;', response.body)
        return api_key.group(1) if api_key else None

    def parse_buyer_reviews(self, response):
        product = response.meta.get('product')
        reqs = response.meta.get('reqs')
        # No review for product - 503 response code
        if response.status == 503:
            product['buyer_reviews'] = ZERO_REVIEWS_VALUE

            if reqs:
                return self.send_next_request(reqs, response)

            return product

        parsed_review = parse_powerreviews_buyer_reviews(response)
        product['buyer_reviews'] = parsed_review if parsed_review else ZERO_REVIEWS_VALUE

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def parse_variant_price(self, response):
        product = response.meta.get('product')
        reqs = response.meta.get('reqs')

        try:
            data = json.loads(response.body)
            prod_data = data.get('result')
            variant_price = prod_data.get('productPrice', {}).get("referencePrice")
            variant_prod_id = prod_data.get('retailSkuId')
        except:
            self.log("Failed parsing json at {} - {}".format(
                response.url, traceback.format_exc()
            ), WARNING)
            variant_price = None
            variant_prod_id = None

        for variant in product['variants']:
            if not variant.get("selected"):
                if variant.get("sku") == variant_prod_id:
                    variant["price"] = variant_price
                    break

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def send_next_request(self, reqs, response):
        req = reqs.pop(0)
        if reqs:
            req.meta["reqs"] = reqs

        return req

    def _scrape_total_matches(self, response):
        try:
            total_matches = int(json.loads(response.body)['result']['totalFull'])
        except Exception as e:
            self.log("Invalid JSON for total matches {}".format(traceback.format_exc()))
            total_matches = 0

        return total_matches

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body)
            prods = data['result'].get('products', [])
        except Exception as e:
            self.log(
                "Failed parsing json at {} - {}".format(response.url, e)
                , WARNING)
            prods = []

        search_term = response.meta['search_term']
        csrf = response.meta.get('csrf')
        api_key = response.meta.get('api_key')
        for prod in prods:
            prod_id = prod.get('id')
            prod_item = SiteProductItem()
            prod_item['asin'] = is_empty(prod.get('asin'))
            req = Request(
                url=self.PROD_URL,
                callback=self.parse_product,
                method="POST",
                body=json.dumps({"sku": prod_id, "origination": "PLP"}),
                meta={
                    "product": prod_item,
                    'search_term': search_term,
                    'remaining': self.quantity,
                    'csrf': csrf,
                    'api_key': api_key
                },
                dont_filter=True,
                headers={
                    "content-type": "application/json",
                    "x-csrf-token": csrf,
                    "X-Requested-With": "XMLHttpRequest",
                    "jet-referer": "/search?term={}".format(search_term),
                },
            )
            yield req, prod_item

    @staticmethod
    def slugify(value):
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
        # Removed .lower() for this website
        value = re.sub('[^\w\s-]', '', value).strip()
        return re.sub('[-\s]+', '-', value)

    def _scrape_next_results_page_link(self, response):
        csrf = self.get_csrf(response) or response.meta.get("csrf")
        api_key = response.meta.get('api_key') or self._get_api_key(response)
        st = response.meta.get("search_term")
        data = self._parse_product_data(response)
        if self.current_page <= data.get('total', 1) // data.get('query', {}).get('size', 24):
            self.current_page += 1
            return Request(
                url=self.SEARCH_URL,
                method="POST",
                body=json.dumps(
                    {
                        "term": st,
                        "origination": "PLP",
                        "page": self.current_page,
                        "sort": self.sort,
                        "zipcode": self.zip
                     }
                ),
                meta={
                    'search_term': st,
                    'csrf': csrf,
                    'api_key': api_key
                },
                dont_filter=True,
                headers={
                    "content-type": "application/json",
                    "x-csrf-token": csrf,
                    "X-Requested-With": "XMLHttpRequest",
                },
            )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def get_csrf(self, response):
        return is_empty(response.xpath('//*[@data-id="csrf"]/@data-val').re('[^\"\']+'))
