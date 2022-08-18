# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

import unicodedata
import re
import json
import traceback
import urlparse
from scrapy.http import Request
from product_ranking.items import SiteProductItem
from product_ranking.spiders.waitrose import WaitroseProductsSpider
from product_ranking.spiders import cond_set_value


class WaitroseCategoriesParser(object):
    def __init__(self, raw_taxonomy):
        self.dic = {}
        self.tree = raw_taxonomy
        self.roots = ["10051", "10052"]

        for root in self.roots:
            self.parse(root)

    def parse(self, root, last_name="shop/browse"):
        name = self.tree.get(root, {}).get('name', '')
        last_name = "/".join([last_name, self.normalize(name)])
        self.dic.update({last_name: root})
        for subroot in self.tree.get(root, {}).get('categoryIds', []):
            self.parse(subroot, last_name)

    @staticmethod
    def normalize(string):
        return string.lower().replace(' ', '_').replace('&', 'and').replace(',', '').replace("'", "")


class WaitroseShelfPagesSpider(WaitroseProductsSpider):
    name = 'waitrose_shelf_urls_products'

    taxonomy_url = "https://www.waitrose.com/api/search-prod/v2/taxonomy"
    browse_url = "https://www.waitrose.com/api/content-prod/v2/cms/publish/productcontent/browse/-1?clientType=WEB_APP"

    def __init__(self, *args, **kwargs):
        self.product_url = kwargs['product_url']
        self.current_page = 1
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(WaitroseShelfPagesSpider, self).__init__(*args, **kwargs)

        self.detect_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_ads = True

    def _start_requests(self, response):
        try:
            body = json.loads(response.body)
        except:
            self.log.error("Got non-API response, check token address")
            return
        else:
            token = body.get('loginResult', {}).get('jwtString')
            self.request_headers['Authorization'] = token
            self.product_url = self.product_url.lower()
            return Request(self.taxonomy_url,
                           callback=self._proceed_initial_requests)

    def _proceed_initial_requests(self, response, categories=None, shelf_url=None):
        if not categories:
            try:
                taxonomy = json.loads(response.body)
                taxonomy = taxonomy.get('taxonomyTree', {}).get('taxonomy', {})
                parser = WaitroseCategoriesParser(taxonomy)
                categories = parser.dic
            except:
                self.log("Failed to send initial request: {}".format(traceback.format_exc()))
                return

        url = self.product_url
        if shelf_url:
            url = shelf_url

        product_query = re.search(r'shop/browse/(.+)', url)
        if not product_query:
            return
        product_query = product_query.group(0)
        category = categories[product_query]
        self.request_body['customerSearchRequest']['queryParams']['category'] = category
        meta = {
            'remaining': self.quantity,
            'search_term': '',
            'offset': 0
        }
        request = Request(
            url=self.SEARCH_URL,
            method='POST',
            body=json.dumps(self.request_body),
            meta=meta,
            dont_filter=True,
            headers=self.request_headers
        )
        if self.detect_ads and not shelf_url:
            meta['categories'] = categories
            request = request.replace(url=self.browse_url, callback=self._start_ads_request, meta=meta)
        elif shelf_url:
            request = request.replace(callback=self._parse_shelf_ads_products, meta=response.meta)
        return request

    def _start_ads_request(self, response):
        meta = response.meta.copy()
        ads = []
        ads_urls = []
        image_urls = []
        try:
            data = json.loads(response.body)
            if data['locations']['header'] and data['locations']['header'][0]:
                ads_products = data['locations']['header'][0]['paragraphSystem']['childComponents']
                for ads_product in ads_products:
                    ads_urls.append(ads_product.get('textArea', {}).get('callToActionURL'))
                    image_url = 'https://ecom.waitrose.com' + ads_product.get('image', {}).get('landscapeImage',
                                                                                               {}).get(
                        'src')
                    image_urls.append(image_url)
            else:
                for temp_data in data['componentsAndProducts']:
                    if 'aemComponent' in temp_data and 'callToActionURL' in temp_data['aemComponent']['textArea']:
                        ads_product = temp_data['aemComponent']
                        ads_urls.append(ads_product.get('textArea', {}).get('callToActionURL'))
                        image_url = 'https://ecom.waitrose.com' + ads_product.get('image', {}).get('landscapeImage',
                                                                                                   {}).get('src')
                        image_urls.append(image_url)
        except:
            self.log("Parse JSON Error {}".format(traceback.format_exc()))

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
            meta['ads'] = ads

            req = Request(
                url=ads_urls[0],
                meta=meta,
                callback=self._get_ads_products,
                dont_filter=True,
                headers=self.request_headers
            )
        else:
            req = Request(
                url=self.SEARCH_URL,
                method='POST',
                body=json.dumps(self.request_body),
                meta=meta,
                dont_filter=True,
                headers=self.request_headers
            )

        return req

    def _get_ads_products(self, response):
        meta = response.meta.copy()
        prods_url = response.xpath('//div[@class="m-product-details-container"]'
                                   '//a[contains(@class, "m-product-open-details")]/@href').extract()
        product_id = None

        if prods_url:
            meta['prod_idx'] = 0
            meta['prods_url'] = prods_url
            prod_url = urlparse.urljoin(response.url, prods_url[0])

            try:
                if 'DisplayProductFlyout' in prod_url:
                    link_id = re.search("productId=(\d+)", prod_url).group(1)
                    product_json = response.xpath('//div[@class="productjson productX is-hidden"]'
                                                  '/@data-json').extract()
                    meta['prod_json_idx'] = 0
                    meta['product_json'] = product_json
                    prod_json = json.loads(product_json[0])
                    if prod_json['productid'] == link_id:
                        prod_num = prod_json['linenumber']
                        parent_cat = prod_json['id']
                        product_id = "{}-{}-{}".format(prod_num, link_id, parent_cat)
                else:
                    product_id = response.url.split('/')[-1]

                return Request(url=self.PRODUCT_URL.format(product_id=product_id),
                               meta=meta,
                               headers=self.request_headers,
                               callback=self._parse_ads_products,
                               dont_filter=True)
            except:
                self.log("Failed to get product ID from response, stopped {}".format(traceback.format_exc()))
        else:
            return self._proceed_initial_requests(
                response,
                categories=response.meta.get('categories'),
                shelf_url=response.url
            )

    def _parse_ads_products(self, response):
        ads = response.meta.get('ads', [])
        ads_idx = response.meta.get('ads_idx')
        ads_urls = response.meta.get('ads_urls')
        prods_url = response.meta.get('prods_url')
        prod_idx = response.meta.get('prod_idx')
        prod_json_idx = response.meta.get('prod_json_idx')
        product_json = response.meta.get('product_json')
        product_list = []
        product_id = None
        data = None
        meta = response.meta

        try:
            data = json.loads(response.body)
            data = data.get('products')[0]
        except:
            self.log('Product extracting failed: {}'.format(traceback.format_exc()))

        products = self._get_products_info(data)
        product_list.extend([prod for prod in products])

        prod_idx += 1
        if prod_idx < len(prods_url):
            prod_url = urlparse.urljoin(response.url, prods_url[prod_idx])

            try:
                prod_json_idx += 1
                if 'DisplayProductFlyout' in prod_url:
                    if prod_json_idx < len(product_json):
                        link_id = re.search("productId=(\d+)", prod_url).group(1)
                        prod_json = json.loads(product_json[prod_json_idx])
                        if prod_json['productid'] == link_id:
                            prod_num = prod_json['linenumber']
                            parent_cat = prod_json['id']
                            product_id = "{}-{}-{}".format(prod_num, link_id, parent_cat)
                            meta['prod_json_idx'] += 1
                else:
                    product_id = response.url.split('/')[-1]
                meta['prod_idx'] += 1

                return Request(url=self.PRODUCT_URL.format(product_id=product_id),
                               meta=meta,
                               headers=self.request_headers,
                               callback=self._parse_ads_products,
                               dont_filter=True)
            except:
                self.log("Failed to get product ID from response, stopped {}".format(traceback.format_exc()))

        if product_list:
            ads[ads_idx]['ad_dest_products'] = product_list

        response.meta['ads'] = ads

        ads_idx += 1
        if ads_idx < len(ads_urls):
            link = ads_urls[ads_idx]
            response.meta['ads_idx'] += 1
            return Request(
                url=link,
                meta=response.meta,
                callback=self._get_ads_products,
                dont_filter=True
            )
        prod = SiteProductItem()
        cond_set_value(prod, 'ads', ads)
        return prod

    def _parse_shelf_ads_products(self, response):
        ads = response.meta.get('ads', [])
        ads_idx = response.meta.get('ads_idx')
        if not response.meta.get('total'):
            response.meta['total'] = self._scrape_total_matches(response)
        try:
            data = json.loads(response.body)
            products_info = [
                {
                    'name': datum.get('searchProduct', {}).get('name'),
                    'reseller_id': datum.get('searchProduct', {}).get('id'),
                    'url': self._parse_url(datum.get('searchProduct', {}).get('name'), datum.get('searchProduct', {}).get('id'))
                }
                for datum in data.get('componentsAndProducts', [])
                if datum.get('searchProduct')
            ]
            if 'ad_dest_products' not in ads[ads_idx]:
                ads[ads_idx]['ad_dest_products'] = []
            ads[ads_idx]['ad_dest_products'] += products_info
            response.meta['ads'] = ads
            response.meta['offset'] = response.meta.get('offset', 0)
            next_request = self._scrape_next_results_page_link(response)
            if next_request:
                return next_request.replace(callback=self._parse_shelf_ads_products)
            elif ads_idx < len(ads) - 1:
                ads_idx += 1
                link = ads[ads_idx]['ad_url']
                response.meta['ads_idx'] += 1
                return Request(
                    url=link,
                    meta=response.meta,
                    callback=self._get_ads_products,
                    dont_filter=True
                )
            prod = SiteProductItem()
            cond_set_value(prod, 'ads', ads)
            return prod
        except:
            self.log('Error Parsing shelf ads inks: {}'.format(traceback.format_exc()))

    def _parse_url(self, name, prod_id):
        return 'https://www.waitrose.com/ecom/products/{name}/{id}'.format(
            name=self._get_url_content_from_name(name),
            id=prod_id
        )

    @staticmethod
    def _get_url_content_from_name(string):
        string = unicodedata.normalize('NFKD', string).encode('ascii', 'ignore')
        string = ''.join(e for e in string if e.isalnum() or e == ' ') if string else ''
        return string.lower().replace(' ', '-')

    def _get_products_info(self, data):
        items = []

        try:
            item = self._get_item(data)
            if item:
                items.append(item)
        except:
            self.log('Can not extract ads products json data: {}'.format(traceback.format_exc()))

        return items

    def _get_item(self, data):
        try:
            return {
                'name': data['shortName'],
                'url': self._parse_url(data['shortName'], data['id']),
                'reseller_id': data['id']
            }
        except:
            self.log("Error".format(traceback.format_exc()))

    def _get_product_links(self, data):
        links = []
        items = data.get('componentsAndProducts', [])
        for item in items:
            product_id = item.get('searchProduct', {}).get('id')
            if product_id:
                link = self.PRODUCT_URL.format(product_id=product_id)
                links.append(link)

        return links

    def _parse_total_matches(self, response):
        return self._scrape_total_matches(response)

    def _scrape_product_links(self, response):
        try:
            body = json.loads(response.body_as_unicode())
        except:
            self.log("Error while extracting product links: {}".format(traceback.format_exc()))
        else:
            items = body.get('componentsAndProducts', [])
            for item in items:
                product_id = item.get('searchProduct', {}).get('id')
                if product_id:
                    yield self.PRODUCT_URL.format(product_id=product_id), SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if self.current_page < self.num_pages:
            self.current_page += 1
            return super(WaitroseShelfPagesSpider, self)._scrape_next_results_page_link(response)