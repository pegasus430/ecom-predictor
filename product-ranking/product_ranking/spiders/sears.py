# -*- coding: utf-8 -*-
import re
import json
import traceback
from urlparse import urljoin, urlparse
import urllib

from scrapy.log import WARNING
from product_ranking.items import Price, SiteProductItem, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults

from scrapy import Request
from scrapy.conf import settings


class SearsProductsSpider(BaseProductsSpider):
    name = 'sears_products'
    allowed_domains = ['sears.com']

    PRODUCT_URL = 'http://www.sears.com/content/pdp/config/products/v1/products/{product_id}?site=sears'
    REVIEW_URL = 'http://www.sears.com/content/pdp/ratings/single/search/Sears/{product_id}&targetType=product&limit=10&offset=0'
    HEADERS = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Encoding': 'gzip, deflate, sdch',
        'Accept-Language': 'en-US,en;q=0.8',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Host': 'www.sears.com',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.82 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest'
    }

    SEARCH_URL = 'http://www.sears.com/service/search/v2/productSearch' \
                 '?catalogId=12605&keyword={search_term}&pageNum={page_num}' \
                 '&rmMattressBundle=true&searchBy=keyword&storeId={store}&tabClicked=All&visitorId=Test&zip={zip_code}'

    HELP_SEARCH_URL = 'http://www.sears.com/browse/services/v1/hierarchy/fetch-paths-by-id/{id}?clientId=obusearch&site=sears'

    REDIRECTED_SEARCH_URL = 'http://www.sears.com/service/search/v2/productSearch' \
                            '?catalogId=12605' \
                            '&catgroupId={cat_gp_id}' \
                            '&pageNum={page_num}' \
                            '&catgroupIdPath={id_path}' \
                            '&levels={level}&primaryPath={level}' \
                            '&redirectType=BRAT_RULE' \
                            '&rmMattressBundle=true' \
                            '&searchBy=subcategory' \
                            '&storeId={store}' \
                            '&tabClicked=All' \
                            '&visitorId=Test' \
                            '&zip={zip_code}'

    handle_httpstatus_list = [404]

    def __init__(self, *args, **kwargs):
        self.store = kwargs.get('store', 10153)
        self.zip_code = kwargs.get('zip_code', 95141)
        url_formatter = FormatterWithDefaults(store=self.store, zip_code=self.zip_code, page_num=1)
        retry_http_codes = settings.get('RETRY_HTTP_CODES')
        if 404 in retry_http_codes:
            retry_http_codes.remove(404)
        super(SearsProductsSpider, self).__init__(
            url_formatter=url_formatter,
            *args,
            **kwargs
        )

    def start_requests(self):
        for req in super(SearsProductsSpider, self).start_requests():
            if self.product_url:
                reseller_id = self._parse_reseller_id(self.product_url.split('?')[0])
                if reseller_id:
                    prod = req.meta.get('product')
                    cond_set_value(prod, 'reseller_id', reseller_id)
                    req = req.replace(url=self.PRODUCT_URL.format(product_id=reseller_id))
                else:
                    self.log('Can not extract product_id from {}'.format(self.product_url), WARNING)
                    continue
            else:
                req = req.replace(callback=self._parse_search)
            req = req.replace(headers=self.HEADERS, dont_filter=True)
            yield req

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):

        product = response.meta.get('product', SiteProductItem())

        try:
            product_json = json.loads(response.body)
            product_json = product_json.get('data')
        except:
            self.log('Error Parsing Product Json: {}'.format(traceback.format_exc()), WARNING)
            return product

        title = self._parse_title(product_json)
        cond_set_value(product, 'title', title)

        image_url = self._parse_image(product_json)
        cond_set_value(product, 'image_url', image_url)

        brand = self._parse_brand(product_json)
        cond_set_value(product, 'brand', brand)

        model = self._parse_model(product_json)
        cond_set_value(product, 'model', model)

        upc = self._parse_upc(product_json)
        cond_set_value(product, 'upc', upc)

        categories = self._parse_categories(product_json)
        cond_set_value(product, 'categories', categories)

        if categories:
            department = categories[-1]
            cond_set_value(product, 'department', department)

        variants = self._parse_variants(product_json)
        cond_set_value(product, 'variants', variants)

        store = self._parse_store(product_json)
        cond_set_value(product, 'store', store)

        cond_set_value(product, 'zip_code', self.zip_code)

        reseller_id = self._parse_reseller_id(response.url)
        cond_set_value(product, 'reseller_id', reseller_id)

        product['locale'] = "en-US"

        reqs = []

        price_requests = self._parse_price_request(response, product_json)
        if price_requests:
            reqs += price_requests

        product_id = self._parse_product_id(product_json)
        if product_id:
            review_url = self.REVIEW_URL.format(product_id=product_id)
            reqs.append(
                Request(
                    review_url,
                    callback=self._parse_reviews,
                    meta=response.meta
                )
            )

        if reqs:
            response.meta['reqs'] = reqs[1:] if reqs[1:] else None
            return reqs[0]
        return product

    @staticmethod
    def _parse_title(product_json):
        title = product_json.get('product', {}).get('name')
        return title

    def _parse_image(self, product_json):
        try:
            img = product_json.get('product', {}).get('assets', {}).get('imgs', [])[0].get('vals', [])[0]
            if img.get('img', {}).get('attrs', {}):
                img = img.get('img', {}).get('attrs', {})
            return img.get('src')
        except:
            self.log('Error parsing image_url:{}'.format(traceback.format_exc()), WARNING)

    @staticmethod
    def _parse_brand(product_json):
        return product_json.get('product', {}).get('brand', {}).get('name')

    @staticmethod
    def _parse_model(product_json):
        if product_json.get('offer'):
            return product_json.get('offer', {}).get('modelNo')
        else:
            return product_json.get('product').get('mfr', {}).get('modelNo')

    @staticmethod
    def _parse_upc(product_json):
        return product_json.get('offer', {}).get('altIds', {}).get('upc') if product_json.get('offer') else None

    @staticmethod
    def _parse_categories(product_json):
        return map(lambda c: c['name'], product_json.get('productmapping', {}).get('primaryWebPath', []))

    @staticmethod
    def _parse_store(product_json):
        return product_json.get('config', {}).get('storeConfig', {}).get('storeId')

    @staticmethod
    def _parse_variants(product_json):
        variants = []

        for variant in product_json.get('attributes', {}).get('variants', []):
            v = {
                'in_stock': variant.get('isAvailable'),
                'properties': {},
                'selected': False
            }

            for attribute in variant['attributes']:
                v['properties'][attribute['name']] = attribute['value']
            variants.append(v)

        if variants:
            return variants

    def _parse_price_request(self, response, product_json):
        price_reuests = []
        product_id = self._parse_product_id(product_json)
        # check if product is bundle
        if 'bundle' in product_json:
            body = {
                "price-request": {
                    "store-id": int(self._parse_store(product_json)),
                    "member-type": "G",
                    "site": product_json.get('config', {}).get('storeName', '').lower(),
                    "storeunit-number": "",
                    "price-identifier": []
                }
            }
            prod_list = []
            quantities_dic = {}
            for bundle in product_json.get('bundle', {}).get('bundleGroup', []):
                if bundle.get('type', '') == 'required':
                    sublist = []
                    for prod in bundle.get('products', []):
                        body['price-request']['price-identifier'].append({
                            'pid': prod.get('id', '')[:-1],
                            'quantity': int(prod.get('quantity')),
                            "pid-type": 0
                        })
                        quantities_dic[prod.get('id', '')[:-1]] = int(prod.get('quantity'))
                        sublist.append(prod.get('id', '')[:-1])
                    prod_list.append(sublist)

            if product_id:
                url = 'http://www.sears.com/content/pdp/v2/pricing/{product_id}' \
                      '/bundle'.format(product_id=product_id)
                meta = response.meta.copy()
                meta['prod_list'] = prod_list
                meta['quantities_dic'] = quantities_dic
                meta['formdata'] = body
                return [
                    Request(
                        url,
                        method='POST',
                        body=json.dumps(body),
                        callback=self._parse_bundle_prods,
                        dont_filter=True,
                        meta=meta,
                    )
                ]

        # there are two types of url for product price
        if 'uid' in product_json.get('productstatus'):
            uid = product_json.get('productstatus', {}).get('uid')
            if product_id and uid:
                price_reuests.append(
                    Request(
                        'http://www.sears.com/content/pdp/v1/products/{product_id}'
                        '/variations/{uid}/ranked-sellers?site=sears'.format(product_id=product_id, uid=uid),
                        callback=self._parse_price,
                        meta=response.meta
                    )
                )

        ssin = product_json.get('productstatus', {}).get('ssin')
        if ssin:
            price_reuests.append(
                Request(
                    'http://www.sears.com/content/pdp/products/pricing/v2/get/price/display/json?ssin={}'
                    '&priceMatch=Y&memberType=G&urgencyDeal=Y&site=SEARS'.format(ssin),
                    callback=self._parse_second_price,
                    headers={'AuthID': 'aA0NvvAIrVJY0vXTc99mQQ=='},
                    meta=response.meta
                )
            )
        return price_reuests if price_reuests else None

    def _parse_price(self, response):
        product = response.meta['product']
        reqs = response.meta.get('reqs', [])
        try:
            data = json.loads(response.body)
            current_price = data['data']['sellers']['groups'][0]['offers'][0]['totalPrice']
            if not current_price:
                raise Exception
            price = Price(price=current_price, priceCurrency='USD')
            cond_set_value(product, 'price', price)
        except:
            self.log('Can not extract price from {}'.format(response.url), WARNING)

        if reqs:
            response.meta['reqs'] = reqs[1:] if reqs[1:] else None
            return reqs[0].replace(meta=response.meta)
        return product

    def _parse_second_price(self, response):
        product = response.meta['product']
        reqs = response.meta.get('reqs', [])
        try:
            price_data = json.loads(response.body)
            current_price = price_data['priceDisplay']['response'][0]['prices']['finalPrice']['min']
            if not current_price:
                raise Exception
            price = Price(price=current_price, priceCurrency='USD')
            cond_set_value(product, 'price', price)
            old_price = price_data['priceDisplay']['response'][0]['prices']['regularPrice']['min']

            if old_price:
                if old_price != current_price:
                    cond_set_value(product, 'was_now', ','.join([str(current_price), str(old_price)]))
                    cond_set_value(product, 'promotions', True)
                save_percent = price_data['priceDisplay']['response'][0]['savings'].get('percentNumeric')
                cond_set_value(product, 'save_percent', save_percent)
                save_amount = price_data['priceDisplay']['response'][0]['savings'].get('dollarNumeric')
                cond_set_value(product, 'save_amount', save_amount)
            else:
                cond_set_value(product, 'promotions', False)

        except:
            self.log('Can not extract price from {}'.format(response.url), WARNING)

        if reqs:
            response.meta['reqs'] = reqs[1:] if reqs[1:] else None
            return reqs[0].replace(meta=response.meta)

        return product

    def _parse_bundle_prods(self, response):
        reqs = response.meta.get('reqs', [])
        prod_list = response.meta.get('prod_list')
        quantities_dic = response.meta.get('quantities_dic')
        formdata = response.meta.get('formdata')
        try:
            data = json.loads(response.body)
            data = data.get('data', {}).get('price-response', {}).get('price-identifier', [])
            converted_dic = {
                prod.get('pid'): float(
                    prod.get('price', {}).get('product-price', {}).get('sale-price', {}).get('price', '0.00'))
                for prod in data
                if prod.get('pid')
                }
            result = {}
            for idx, type in enumerate(prod_list):
                for pid in type:
                    if (idx not in result or converted_dic[result[idx]] > converted_dic[pid]) and converted_dic[pid] != 0:
                        result[idx] = pid
            formdata['price-request']['price-identifier'] = [
                {
                    'quantity': quantities_dic[pid],
                    'pid': pid,
                    "pid-type": 0
                }
                for pid in result.values()
                ]
            url = response.url + '/savestory'
            return Request(
                url,
                method='POST',
                body=json.dumps(formdata),
                callback=self._parse_bundle_price,
                dont_filter=True,
                meta=response.meta,
            )
        except:
            self.log('Error Parsing Bundle Price: {}'.format(traceback.format_exc()), WARNING)

        if reqs:
            return self.send_next_request(reqs)

    def _parse_bundle_price(self, response):
        reqs = response.meta.get('reqs', [])
        product = response.meta.get('product')
        try:
            data = json.loads(response.body)
            data = data.get('data', {})
            price = data.get('displayPrice', {}).get('numericValue')
            if price:
                cond_set_value(product, 'price', Price(price=price, priceCurrency='USD'))
            old_price = data.get('oldPrice', {}).get('numericValue', 0)
            if old_price != price:
                cond_set_value(product, 'promotions', True)
                cond_set_value(product, 'was_now', ','.join([str(price), str(old_price)]))
                save = data.get('savings', {}).get('numericValue')
                cond_set_value(product, 'save_amount', save)
            else:
                cond_set_value(product, 'promotions', False)
        except:
            self.log('Error Parsing the Bundle Price: {}'.format(traceback.format_exc()), WARNING)

        if reqs:
            response.meta['reqs'] = reqs[1:] if reqs[1:] else None
            return reqs[0].replace(meta=response.meta)
        return product

    def _parse_reviews(self, response):
        reqs = response.meta['reqs']
        product = response.meta['product']
        try:
            reviews = json.loads(response.body)
            rating_by_star = {
                review.get('name', ''): int(review.get('count', 0))
                for review in reviews.get('data', {}).get('overall_rating_breakdown', [])
                if review.get('name') and review.get('count')
                }
            num_of_reviews = reviews.get('data', {}).get('review_count', 0)
            average_rating = reviews.get('data', {}).get('overall_rating', '0')
            if rating_by_star:
                product["buyer_reviews"] = BuyerReviews(
                    num_of_reviews=num_of_reviews,
                    average_rating=float(average_rating),
                    rating_by_star=rating_by_star,
                )
        except:
            self.log('Error Parsing Product review: {}'.format(traceback.format_exc()), WARNING)

        if reqs:
            response.meta['reqs'] = reqs[1:] if reqs[1:] else None
            return reqs[0].replace(meta=response.meta)

        return product

    @staticmethod
    def _parse_product_id(product_json):
        return product_json.get('product', {}).get('id')

    def _parse_search(self, response):
        try:
            data = json.loads(response.body)
            data = data.get('data', {})
            if data.get('redirect') and data.get('redirect', {}).get('url'):
                redirect_id = urlparse(data.get('redirect', {}).get('url')).path.split('/')[-1].replace('b-', '')
                url = self.HELP_SEARCH_URL.format(id=redirect_id)
                return Request(
                    url,
                    callback=self._parse_redirected_search,
                    meta=response.meta,
                )

            if not response.meta.get('total_matches'):
                response.meta['total_matches'] = data.get('productCount', 0)
            product_links = [
                urljoin(response.url, prod.get('url'))
                for prod in data.get('products', [])
            ]
            if not product_links:
                raise Exception
            response.meta['product_links'] = product_links
            current_page = data.get('currentPageNumber', 1)
            next_link = None
            for page in data.get('pagination', []):
                if current_page + 1 == int(page.get('id')) and page.get('value'):
                    if response.meta.get('redirect_search_params'):
                        params = response.meta.get('redirect_search_params')
                        next_link = self.REDIRECTED_SEARCH_URL.format(
                            cat_gp_id=params.get('cat_gp_id'),
                            level=params.get('level'),
                            id_path=params.get('id_path'),
                            store=self.store,
                            zip_code=self.zip_code,
                            page_num=current_page+1
                        )
                    else:
                        next_link = self.SEARCH_URL.format(
                            page_num=current_page+1,
                            store=self.store,
                            zip_code=self.zip_code,
                            search_term=response.meta.get('search_term')
                        )
                    break
            response.meta['next_link'] = next_link
            return self.parse(response)
        except:
            self.log('Error Parsing Json from :{}'.format(traceback), WARNING)

    def _parse_redirected_search(self, response):
        try:
            data = json.loads(response.body)
            data = data.get('data')[0]
            cat_gp_id = data.get('catgroupId')
            level = urllib.quote_plus(data.get('catgroups')[0].get('namePath'))
            id_path = data.get('catgroups')[0].get('idPath')
            url = self.REDIRECTED_SEARCH_URL.format(
                level=level,
                cat_gp_id=cat_gp_id,
                id_path=id_path,
                store=self.store,
                zip_code=self.zip_code,
                page_num=1
            )
            response.meta['redirect_search_params'] = {
                'cat_gp_id': cat_gp_id,
                'level': level,
                'id_path': id_path
            }
            return Request(
                url,
                callback=self._parse_search,
                meta=response.meta
            )
        except:
            self.log('Error Parsing Redirected url: {}'.format(traceback.format_exc()), WARNING)

    @staticmethod
    def _parse_reseller_id(url):
        product_id = re.search('p-(.*)', url.split('/')[-1])
        return product_id.group(1) if product_id else None

    def _scrape_next_results_page_link(self, response):
        next_link = response.meta.get('next_link')
        if next_link:
            return Request(
                next_link,
                meta=response.meta,
                callback=self._parse_search,
                headers=self.HEADERS
            )

    def _scrape_product_links(self, response):
        links = response.meta.get('product_links', [])
        for link in links:
            prod = SiteProductItem()
            cond_set_value(prod, 'url', link)
            reseller_id = self._parse_reseller_id(link)
            if reseller_id:
                cond_set_value(prod, 'reseller_id', reseller_id)
                api_link = self.PRODUCT_URL.format(product_id=reseller_id)
                yield api_link, prod

    def _get_products(self, response):
        for req in super(SearsProductsSpider, self)._get_products(response):
            yield req.replace(headers=self.HEADERS, dont_filter=True)
