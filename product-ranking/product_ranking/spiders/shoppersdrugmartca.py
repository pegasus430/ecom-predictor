from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback
import urllib

from scrapy.http import Request

from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from urlparse import urljoin

class ShoppersdrugmartCaProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'shoppersdrugmartca_products'
    allowed_domains = ["www1.shoppersdrugmart.ca"]

    REVIEW_URL = 'https://api.bazaarvoice.com/data/batch.json' \
                 '?passkey=caX7JsVasecVzM59tquUbkFfzRcA0T09c47X1SmsB70d8' \
                 '&apiversion=5.5&displaycode=11365-en_ca' \
                 '&resource.q0=products' \
                 '&filter.q0=id%3Aeq%3A{product_id}' \
                 '&stats.q0=reviews&filteredstats.q0=reviews' \
                 '&filter_reviews.q0=contentlocale%3Aeq%3Afr%2Cen_CA' \
                 '&filter_reviewcomments.q0=contentlocale%3Aeq%3Afr%2Cen_CA'

    SEARCH_URL = 'https://www1.shoppersdrugmart.ca/en/search?query={search_term}'

    SEARCH_POST_URL = 'https://www1.shoppersdrugmart.ca/Search/GetAllResultsByQuery'

    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.8',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Host': 'www1.shoppersdrugmart.ca',
        'Origin': 'https://www1.shoppersdrugmart.ca',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/57.0.2987.110 Safari/537.36',
        'X-NewRelic-ID': '',
        'X-Requested-With': 'XMLHttpRequest'
    }

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)
        super(ShoppersdrugmartCaProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def start_requests(self):
        for req in super(ShoppersdrugmartCaProductsSpider, self).start_requests():
            if not self.product_url:
                req = req.replace(
                    callback=self._parse_help)
            yield req

    def _get_form_data(self, response, product_data={}):
        form_data = response.meta.get('form_data', {})
        next_page = product_data.get('SwiftypeResults', {}).get('info', {}).get('page', {}).get('current_page', 0) + 1
        if not form_data:
            session = response.xpath('//input[@name="intelliSession"]/@value').extract()
            it_id = response.xpath('//input[@name="intelliInterface"]/@value').extract()
            res_id = response.xpath('//input[@name="intelliQuestionId"]/@value').extract()
            xid = re.search(r'xpid:"(.*?)"', response.body)

            if not all([session, it_id, res_id, xid]):
                self.log('Can not extract the session')
                return
            self.headers['X-NewRelic-ID'] = xid.group(1)
            session = session[0]
            it_id = it_id[0]
            res_id = res_id[0]
            st = response.meta.get('search_term')
            form_data = {
                'query': st,
                'numRes': '18',
                'facets': 'type,sections',
                'filters': 'type,Product,',
                'getFilters': True,
                'intelliResponseSession': session,
                'intelliInterfaceID': it_id,
                'irResponseId': res_id
            }
        if product_data:
            brands = [
                'BR:{}'.format(i)
                for i in product_data
                    .get('SwiftypeResults', {}).get('info', {}).get('page', {}).get('facets', {}).get('br', [])
            ]
            form_data['filters'] = (','.join(['type', 'Product'] + brands) + ',').encode('UTF-8')
            form_data['getFilters'] = False
        form_data['page'] = next_page
        return form_data

    def _parse_help(self, response, product_data={}):
        form_data = self._get_form_data(response, product_data)
        response.meta['form_data'] = form_data
        return Request(
            self.SEARCH_POST_URL,
            method='POST',
            body=urllib.urlencode(form_data),
            meta=response.meta,
            headers=self.headers,
            dont_filter=True
        )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        
        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        desc = self._parse_description(response)
        cond_set_value(product, 'description', desc)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        if sku:
            return Request(
                url=self.REVIEW_URL.format(product_id=sku),
                dont_filter=True,
                callback=self.br._parse_buyer_reviews_from_filters,
                meta={
                    'product': product
                }
            )

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//meta[@property="og:title"]/@content').extract()
        return title[0] if title else None

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//meta[@name="br"]/@content').extract()
        return brand[0] if brand else None

    @staticmethod
    def _parse_image(response):
        image = response.xpath('//meta[@property="og:image"]/@content').extract()
        return urljoin(response.url, image[0]) if image else None

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath('//section[@class="md-pdp-spec-section" and h3[@class="md-pdp-spec-name"]/text()="SKU"]'
                             '/div[@class="md-pdp-spec-value"]/text()').extract()
        return sku[0] if sku else None

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = re.search(r'details\/(\d+)', response.url)
        return reseller_id.group(1) if reseller_id else None

    @staticmethod
    def _parse_description(response):
        description = response.xpath('//meta[@name="description"]/@content').extract()
        return description[0] if description else None

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body)
            for item in data.get('SwiftypeResults', {}).get('records', {}).get('page', []):
                url = item.get('url')
                if url:
                    yield url, SiteProductItem()
        except:
            self.log('No product links:{}'.format(traceback.format_exc()))

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body)
            return data.get('SwiftypeResults', {}).get('info', {}).get('page', {}).get('total_result_count')
        except:
            self.log('Error Parsing Total_matches:{}'.format(traceback.format_exc()))

    def _scrape_next_results_page_link(self, response):
        try:
            data = json.loads(response.body)
            current_page = data.get('SwiftypeResults', {}).get('info', {}).get('page', {}).get('current_page')
            total_pages = data.get('SwiftypeResults', {}).get('info', {}).get('page', {}).get('num_pages')
            if current_page <= total_pages:
                return self._parse_help(response, product_data=data)
        except:
            self.log('Error Parsing next page link:{}'.format(traceback.format_exc()))

    def _get_products(self, response):
        for req in super(ShoppersdrugmartCaProductsSpider, self)._get_products(response):
            yield req.replace(dont_filter=True)
