# -*- coding: utf-8 -*-

import json
import traceback
import math
from scrapy.conf import settings

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.powerreviews import parse_powerreviews_buyer_reviews

from scrapy import Request
from scrapy.log import DEBUG


class BJSProductsSpider(BaseProductsSpider):
    name = 'bjs_products'
    allowed_domains = ['bjs.com', 'bjswholesale-cors.groupbycloud.com', 'readservices-b2c.powerreviews.com']

    SEARCH_URL = "https://bjswholesale-cors.groupbycloud.com/api/v1/search"
    PRODUCT_URL = "https://api.bjs.com/digital/live/api/v1.0/pdp/10201?productId={product_id}&pageName=PDP&clubId=0096"
    REVIEW_URL = "http://readservices-b2c.powerreviews.com/m/9794/l/en_US/product/{part_num}/reviews?"

    payload = {
        "area": "BCProduction",
        "biasing": {"biases": []},
        "collection": "productionB2CProducts",
        "excludedNavigations": ['visualVariant.nonvisualVariant.availability'],
        "fields": ['*'],
        "pageSize": 40,
        "query": "",
        "refinements": [],
        "skip": 0,
        "sort": {
            "field": "_relevance",
            "order": "Descending"
        }
    }

    headers = {
        'Accept-Encoding': 'gzip, deflate, br',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36'
    }

    def __init__(self, *args, **kwargs):
        self.total_matches = None
        super(BJSProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)
        self.user_agent = 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        for request in super(BJSProductsSpider, self).start_requests():
            if not self.product_url:
                data = self.payload.copy()
                data['query'] = self.searchterms[0]
                data['skip'] = 0

                request = request.replace(url=self.SEARCH_URL, method="POST", body=json.dumps(data),
                                          headers=self.headers,
                                          meta={'search_term': self.searchterms[0], 'remaining': self.quantity})
            if self.product_url:
                prod = SiteProductItem()
                prod['is_single_result'] = True
                prod['url'] = self.product_url
                prod['search_term'] = ''

                product_id = self.product_url.split('/')[-1]
                url = self.PRODUCT_URL.format(product_id=product_id)
                request = request.replace(url=url, callback=self._parse_single_product, meta={'product': prod})

            yield request

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        if self.total_matches:
            return self.total_matches
        try:
            contents = json.loads(response.body)
            self.total_matches = int(contents.get('totalRecordCount'))
            return self.total_matches
        except Exception as e:
            self.log("Exception looking for total_matches {}".format(e), DEBUG)
        finally:
            self.total_matches = 0

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        current_page = meta.get('current_page', 1)
        total_matches = self._scrape_total_matches(response)
        results_per_page = self._scrape_results_per_page(response)
        if not results_per_page:
            results_per_page = 40
        if total_matches and current_page < math.ceil(total_matches / float(results_per_page)):
            current_page += 1
            st = response.meta['search_term']
            data = self.payload.copy()
            data['query'] = st
            data['skip'] = (current_page - 1) * 40
            meta['current_page'] = current_page
            return Request(
                url=self.SEARCH_URL, method="POST", body=json.dumps(data), headers=self.headers, meta=meta)

    def _scrape_product_links(self, response):
        links = []
        try:
            contents = json.loads(response.body)
            for record in contents.get('records', []):
                link = 'https://www.bjs.com' + record.get('allMeta', {}).get('visualVariant')[0].get('nonvisualVariant', [])[0].get('product_url')
                links.append(link)
        except Exception as e:
            self.log("Exception looking for product links {}".format(e), DEBUG)
        finally:
            for link in links:
                prod = SiteProductItem()
                prod['url'] = link
                prod_id = link.split('/')[-1]
                link = self.PRODUCT_URL.format(product_id=prod_id)
                yield link, prod

    @staticmethod
    def _parse_title(data):
        title = data.get('description', {}).get('name')
        return title

    def _parse_price(self, data):
        price = data.get('maximumItemPrice', {})
        if not price:
            price = data.get('bjsClubProduct', [{}])[0].get('clubItemStandardPrice', {})
        try:
            return Price(price=float(price.get('amount')), priceCurrency='USD') if price else None
        except:
            self.log('Error Parsing Price: {}'.format(traceback.format_exc()))

    @staticmethod
    def _parse_image(data):
        images = data.get('productImages', {}).get('fullImage')
        return images

    def _parse_categories(self, data):
        category_list = []
        try:
            categories_info = data.get('breadCrumbDetail')
            category_level = categories_info.get('Levels')
            for index in range(1, category_level + 1):
                category = categories_info.get('Level{}'.format(index)).split('||')[-1]
                category_list.append(category)
            return category_list
        except:
            self.log("Error while parsing categories {}".format(traceback.format_exc()))

    @staticmethod
    def _search_attribute(attribute_name, data):
        if data.get('descriptiveAttributes'):
            for attr in data.get('descriptiveAttributes'):
                if attr.get('name') == attribute_name:
                    return attr.get('attributeValueDataBeans', [{}])[0].get('value')

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        try:
            data = json.loads(response.body_as_unicode())
        except:
            self.log('JSON not found or invalid JSON: {}'
                     .format(traceback.format_exc()))
            product['not_found'] = True
            return product

        title = self._parse_title(data)
        if title is None:
            product["no_longer_available"] = True
            return product
        cond_set_value(product, 'title', title)

        price = self._parse_price(data)
        cond_set_value(product, 'price', price)

        image_url = self._parse_image(data)
        cond_set_value(product, 'image_url', image_url)

        brand = guess_brand_from_first_words(product['title'])
        cond_set_value(product, 'brand', brand)

        if data.get('bjsitems', []):
            sku = data.get('bjsitems', [])[0].get('articleId')
            cond_set_value(product, 'sku', sku)
            cond_set_value(product, 'reseller_id', sku)

        model = data.get('manufacturerPartNumber')
        cond_set_value(product, 'model', model)

        upc = self._search_attribute('upc', data)
        cond_set_value(product, 'upc', upc)

        categories = self._parse_categories(data)
        cond_set_value(product, 'categories', categories)

        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Available Online: 1 or 0 (1 = yes, 0 = no)
        if data.get('bjsClubProduct', []):
            online_avail = data.get('bjsClubProduct', [])[0].get('itemAvailableOnline', 'N')
            product['available_online'] = 1 if online_avail == 'Y' else 0

        # Available In-club(store): 1 or 0 (1 = yes, 0 = no)
        if data.get('bjsClubProduct', []):
            club_avail = data.get('bjsClubProduct', [])[0].get('itemAvailableInClub', 'N')
            product['available_store'] = 1 if club_avail == 'Y' else 0

        product['is_out_of_stock'] = str(data.get('description', {}).get('available')) == '0'

        product['is_in_store_only'] = str(product.get('available_online', None)) == '0' and str(
            product.get('available_store', None)) == '1'

        product['locale'] = "en-US"

        part_number = data.get('partNumber')

        if part_number:
            url = self.REVIEW_URL.format(part_num=part_number)
            return Request(url=url,
                           callback=self._parse_reviews,
                           meta={'product': product},
                           headers={'authorization': '7c12e7e9-fe30-4e7a-bcb8-8376b9117a6b'},
                           dont_filter=True)

        return product

    @staticmethod
    def _parse_reviews(response):
        meta = response.meta
        product = meta.get('product')
        cond_set_value(product, 'buyer_reviews', parse_powerreviews_buyer_reviews(response))

        return product
