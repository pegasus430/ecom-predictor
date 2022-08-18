import json
import traceback
import urllib
from datetime import datetime

import boto
from boto.s3.key import Key
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import SiteProductItem
from product_ranking.spiders import cond_set_value
from scrapy import Field, Request
from scrapy.log import ERROR

from .sainsburys_uk import SainsburysProductsSpider


class SainsburysUkInStoreSpiderItem(SiteProductItem):
    zip_code_data = Field()


class SainsburysUkInStoreSpider(SainsburysProductsSpider):
    name = 'sainsburys_uk_in_store_products'

    allowed_domains = ['sainsburys.co.uk']

    stores_api = 'https://api.stores.sainsburys.co.uk/v1/stores/?api_client_id=slfe&page={page}'

    bucket = 'sc-settings'
    bucket_key = 'sainsburys_all_zip_codes'

    all_zip_codes = []

    user_agent = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:55.0) Gecko/20100101 Firefox/55.0"

    def __init__(self, *args, **kwargs):
        super(SainsburysUkInStoreSpider, self).__init__(*args, **kwargs)

        self.zip_codes = kwargs.get('zip_code')

        self.product = SainsburysUkInStoreSpiderItem()
        self.product['zip_code_data'] = []

    def _loads_all_zip_codes(self):
        try:
            s3_conn = boto.connect_s3(is_secure=False)
            s3_bucket = s3_conn.get_bucket(self.bucket, validate=False)
            zip_codes = s3_bucket.get_key(self.bucket_key)

            if zip_codes:
                date = zip_codes.last_modified
                date = datetime.strptime(date, '%a, %d %b %Y %H:%M:%S GMT')

                if (datetime.now() - date).days <= 7:
                    data = zip_codes.get_contents_as_string()
                    datalist = data.split(',')
                    self.log("Loaded zipcodes: {}".format(len(datalist)))
                    return datalist
        except:
            self.log('Can not retrieve zip codes: {}'.format(traceback.format_exc()), level=ERROR)

        return []

    @staticmethod
    def _cleanup_list(list_to_cleanup):
        return list(set([a.strip() for a in list_to_cleanup if a.strip()]))

    def _save_all_zip_codes(self, all_zip_codes):
        try:
            s3_conn = boto.connect_s3(is_secure=False)
            s3_bucket = s3_conn.get_bucket(self.bucket, validate=False)
            zip_codes = Key(s3_bucket)
            zip_codes.key = self.bucket_key

            zip_codes.set_contents_from_string(','.join(all_zip_codes))
        except:
            self.log('Can not save zip codes: {}'.format(traceback.format_exc()), level=ERROR)

    def start_requests(self):
        self.product['is_single_result'] = True
        self.product['url'] = self.product_url
        self.product['search_term'] = ''

        self.all_zip_codes = self._loads_all_zip_codes()
        self.zip_codes = map(lambda x: x.strip(), self.zip_codes.split(',')) if self.zip_codes else self.all_zip_codes

        if not self.zip_codes:
            page = 1

            yield Request(
                self.stores_api.format(page=page),
                callback=self._parse_stores,
                meta={'page': page}
            )
        else:
            yield self._process_zip_codes()

    def _parse_stores(self, response):
        try:
            data = json.loads(response.body)

            self.zip_codes.extend(map(lambda x: x['contact']['post_code'], data['results']))

            if data['page_meta']['offset'] < data['page_meta']['total'] + data['page_meta']['limit']:
                page = response.meta['page'] + 1

                return Request(
                    self.stores_api.format(page=page),
                    callback=self._parse_stores,
                    meta={'page': page}
                )
            else:
                self.zip_codes = self._cleanup_list(self.zip_codes)
                self._save_all_zip_codes(self.zip_codes)

                return self._process_zip_codes()
        except:
            self.log('Can not parse zip codes: {}'.format(traceback.format_exc()))

    def _process_zip_codes(self):
        if self.zip_codes:
            zip_code = self.zip_codes.pop(0)
            self.log('Processing zip code: {}'.format(zip_code))

            body = {
                'langId': '44',
                'storeId': 10151,
                'currentPageUrl': '',
                'messageAreaId': 'PostCodeMessageArea',
                'currentViewName': 'ProductDisplayView',
                'postCode': zip_code
            }

            return Request(
                'https://www.sainsburys.co.uk/shop/CheckPostCode',
                method='POST',
                body=urllib.urlencode(body),
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                callback=self._select_zip_code,
                meta={
                    'zip_code': zip_code,
                    'dont_redirect': True,
                    'handle_httpstatus_list': [302]
                },
                dont_filter=True
            )
        else:
            return self.product

    def _select_zip_code(self, response):
        for req in super(SainsburysUkInStoreSpider, self).start_requests():
            yield req.replace(meta=response.meta.copy(), dont_filter=True)

    def parse_product(self, response):
        if not self.product.get('title'):
            title = self._parse_title(response)
            cond_set_value(self.product, 'title', title)

        if not self.product.get('brand'):
            title = self._parse_title(response)

            if title:
                brand = guess_brand_from_first_words(title)
                cond_set_value(self.product, 'brand', brand)

        if not self.product.get('reseller_id'):
            reseller_id = self._parse_reseller_id(response)
            cond_set_value(self.product, 'reseller_id', reseller_id)
            cond_set_value(self.product, 'upc', reseller_id)

        if not self.product.get('image_url'):
            image_url = self._parse_image_url(response)
            cond_set_value(self.product, 'image_url', image_url)

        price = self._parse_price(response)

        zip_code_data = {
            'zip_code': response.meta['zip_code'],
            'in_stock': not self._parse_no_longer_available(response),
            'price': float(price.price) if price else None,
            'currency': price.priceCurrency if price else None
        }
        self.log('Zip code data: {}'.format(zip_code_data))

        self.product['zip_code_data'].append(zip_code_data)

        return self._process_zip_codes()
