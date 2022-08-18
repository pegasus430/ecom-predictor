from __future__ import division, absolute_import, unicode_literals

import json
import traceback
import re

from scrapy import Request
from scrapy.log import ERROR, WARNING, INFO
from scrapy.conf import settings

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider


class CvsProductsSpider(BaseProductsSpider):
    name = 'cvs_products'
    allowed_domains = ["cvs.com", "api.bazaarvoice.com"]
    start_urls = []

    SEARCH_URL = "https://cvshealth-cors.groupbycloud.com/api/v1/search"

    search_payload = {
        "query": "",
        "fields": ["*"],
        "wildcardSearchEnabled": False,
        "pruneRefinements": False,
        "area": "Production",
        "collection": "productsLeaf",
        "matchStrategyName":"Relaxed",
        "pageSize": 20,
        "visitorId": "cj95qz9p500013179gdk4imj7",
        "sessionId": "cj95qz9p40000317969u93jut"
    }
    product_payload = {
        "query": "",
        "sort": [
            {
                "field": "_relevance",
                "order": "Descending"
            }
        ],
        "fields": ["*"],
        "refinements": [
            {
                "navigationName": "id",
                "value": "",
                "exclude": False,
                "type": "Value"
            }
        ],
        "wildcardSearchEnabled": False,
        "pruneRefinements": False,
        "area": "PDP",
        "collection": "productsLeaf",
        "pageSize": 20,
        "visitorId": "cj95qz9p500013179gdk4imj7",
        "sessionId": "cj95sexg500033179141ddx7t"
    }

    products_per_page = 20

    REVIEW_URL = "http://api.bazaarvoice.com/data/batch.json" \
                 "?passkey=ll0p381luv8c3ler72m8irrwo&apiversion=5.5" \
                 "&displaycode=3006-en_us&resource.q0=reviews" \
                 "&filter.q0=isratingsonly%3Aeq%3Afalse&filter.q0=productid%3Aeq%3A{prod_id}" \
                 "&filter.q0=contentlocale%3Aeq%3Aen_GB%2Cen_US&sort.q0=relevancy%3Aa1&stats.q0=reviews" \
                 "&filteredstats.q0=reviews&include.q0=authors%2Cproducts"

    HEADERS = {'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
               'authority': 'www.cvs.com',
               'upgrade-insecure-requests': '1',
               'scheme': 'https',
               'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.98 Safari/537.36'
               }

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)
        self.referer = None
        self.first_time_products = None
        self.products_per_page = 20
        super(CvsProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        for req in super(CvsProductsSpider, self).start_requests():
            if req.meta.get('search_term'):
                payload = self.search_payload.copy()
                payload['query'] = req.meta['search_term']
                req.meta.update({'payload': payload})
                req = req.replace(url=self.SEARCH_URL,
                                  method='POST',
                                  body=json.dumps(payload))
                yield req
            elif self.product_url:
                sku = self._extract_id_from_url(self.product_url)
                if sku:
                    self.product_payload['refinements'][0]['value'] = sku
                    req = req.replace(url=self.SEARCH_URL, method='POST', body=json.dumps(self.product_payload))
                    yield req
                else:
                    self.log("Failed to parse product sku from url, stopped.", ERROR)

    @staticmethod
    def _extract_id_from_url(url):
        product_id = re.search(r'prodid.{1}(\d+)', url)
        return product_id.group(1) if product_id else None

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        try:
            body = json.loads(response.body_as_unicode())
            item = body.get('records')[0]
            product = self._fill_item(item, SiteProductItem())
            response.meta.update({'product': product, 'product_id': product['sku']})
            return Request(self.REVIEW_URL.format(prod_id=product['sku']),
                           callback=self._parse_reviews,
                           meta=response.meta)
        except:
            self.log("Unable to load json response, product parsing failed: {}".format(traceback.format_exc()))

    def _scrape_total_matches(self, response):
        try:
            body = json.loads(response.body_as_unicode())
            totals = body.get('totalRecordCount')
            return int(totals)
        except:
            self.log("Unable to count total matches, search failed: {}".format(traceback.format_exc()))

    def _scrape_product_links(self, response):
        try:
            body = json.loads(response.body_as_unicode())
            items = body.get('records')
        except:
            self.log("Unable to get json response, search failed: {}".format(traceback.format_exc()))
            return

        if items:
            for item in items:
                filled_item = self._fill_item(item, SiteProductItem())
                yield self.REVIEW_URL.format(prod_id=filled_item['sku']), filled_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _get_products(self, response):
        for req in super(CvsProductsSpider, self)._get_products(response):
            if isinstance(req, Request) and req.meta['product']:
                req = req.replace(callback=self._parse_reviews)
            yield req

    def _fill_item(self, item, product):
        product['title'] = item.get('allMeta', {}).get('title')

        brand = item.get('allMeta', {}).get('ProductBrand_Brand')
        product['brand'] = brand

        product['reseller_id'] = item.get('allMeta', {}).get('id')

        categories = [y for x, y in item.get('allMeta', {}).get('categories', [{}])[0].items()]
        product['categories'] = categories if categories else None
        product['department'] = categories[-1] if categories else None

        try:
            variants = item.get('allMeta', {}).get('variants')
            chosen_variant = variants.pop(0)
            chosen_variant = chosen_variant.get('subVariant')[0]

            oos = chosen_variant.get('p_Product_Availability')
            if oos == "1000":
                product['is_out_of_stock'] = False
            elif oos == "1001":
                product['is_out_of_stock'] = True

            store_only = chosen_variant.get('retail_only')
            product['is_in_store_only'] = (store_only == '1')

            available_online = chosen_variant.get('on_sale')
            product['available_online'] = (available_online == '1')

            image_url = chosen_variant.get('BV_ImageUrl')
            product['image_url'] = image_url
            product['description'] = chosen_variant.get('p_Product_Details')
            product['sku'] = chosen_variant.get('p_Sku_ID')
            product['url'] = chosen_variant.get('BV_ProductPageUrl')
            price = chosen_variant.get('gbi_Actual_Price')
            product['price'] = Price(price=float(price.replace(",", "")), priceCurrency='USD') if price else None
            product['secondary_id'] = product.get('sku')
        except:
            self.log("Failed to get product details: {}".format(traceback.format_exc()))
        finally:
            return product

    def _parse_reviews(self, response):
        product = response.meta['product']
        product_id = product['sku']
        zero_reviews_value = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        try:
            data = json.loads(response.body_as_unicode())

            results = data.get('BatchedResults', {}).get('q0', {}).get('Includes', {}).get('Products', {}).get(
                product_id, {})

            if results:
                data = results.get('FilteredReviewStatistics')
                review_count = data.get('TotalReviewCount')

                rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
                stars = data.get("RatingDistribution", [])
                for star in stars:
                    rating_by_star[str(star['RatingValue'])] = star['Count']

                average_rating = data.get("AverageOverallRating", 0)

                buyer_reviews = {
                    'num_of_reviews': review_count,
                    'average_rating': round(float(average_rating), 1) if average_rating else 0,
                    'rating_by_star': rating_by_star
                }

            else:
                buyer_reviews = zero_reviews_value

        except:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()), WARNING)
            buyer_reviews = zero_reviews_value

        product['buyer_reviews'] = BuyerReviews(**buyer_reviews)

        return product

    def _scrape_next_results_page_link(self, response):
        try:
            total = response.meta.get('total_matches')
            skip = response.meta.get('skip', 0) + self.products_per_page
            if total > skip:
                response.meta['skip'] = skip
                payload = response.meta['payload']
                payload['skip'] = skip
                return Request(
                    self.SEARCH_URL,
                    method='POST',
                    headers=self.HEADERS,
                    body=json.dumps(payload),
                    meta=response.meta,
                    dont_filter=True
                )
        except:
            self.log("Unable to get next page link: {}".format(traceback.format_exc()))
