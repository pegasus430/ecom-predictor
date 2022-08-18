# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

import json
import re
import traceback
import urlparse
import urllib
from scrapy.conf import settings

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider
from product_ranking.spiders import cond_set_value
from scrapy.http import Request
from scrapy import Selector
from scrapy.log import ERROR, WARNING
from product_ranking.utils import is_empty


class GapProductsSpider(BaseProductsSpider):
    name = 'gap_products'
    allowed_domains = ["www.gap.com"]
    start_urls = ["http://www.gap.com"]

    SEARCH_API_URL = "http://www.gap.com/resources/productSearch/v1/{search_term}?&isFacetsEnabled=true" \
                     "&globalShippingCountryCode=pl" \
                     "&globalShippingCurrencyCode=PLN" \
                     "&locale=en_US&"

    SEARCH_URL = "http://www.gap.com/browse/search.do?searchText={search_term}"

    REVIEW_URL = "http://api.bazaarvoice.com/data/batch.json?passkey=tpy1b18t8bg5lp4y9hfs0qm31" \
                 "&apiversion=5.5" \
                 "&displaycode=3755_27_0-en_us" \
                 "&resource.q0=products" \
                 "&filter.q0=id%3Aeq%3A{product_id}" \
                 "&stats.q0=reviews" \
                 "&filteredstats.q0=reviews" \
                 "&filter_reviews.q0=contentlocale%3Aeq%3Aen_CA%2Cen_US" \
                 "&filter_reviewcomments.q0=contentlocale%3Aeq%3Aen_CA%2Cen_US"

    PRODUCT_URL = "http://www.gap.com/browse/product.do?vid={v_id}&pid={p_id}"

    DO_VARIANTS = True

    def __init__(self, *args, **kwargs):
        super(GapProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        for search_term in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(search_term.encode('utf-8')),
                ),
                meta={'search_term': search_term, 'remaining': self.quantity},
                callback=self._parse_helper,
                dont_filter=True
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.product_url,
                          callback=self._parse_single_product,
                          meta={'product': prod},
                          dont_filter=True
                          )

    def _parse_helper(self, response):
        self.search_str = response.meta['search_term'].split()[0].lower()
        return Request(self.SEARCH_API_URL.format(search_term=self.search_str),
                       meta={'search_term': response.meta['search_term'], 'remaining': self.quantity},
                       dont_filter=True)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        is_out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        reseller_id = self._parse_reseller_id(product.get('url', ''))
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        product_id = re.findall(r'"businessCatalogItemId":"(.*?)"', response.body)

        if product_id:
            url = self.REVIEW_URL.format(product_id=product_id[0])
            return Request(
                url=url,
                callback=self._parse_buyer_reviews,
                meta={'product': product},
                dont_filter=True
            )

        return product

    def _parse_title(self, response):
        title = response.xpath('//*[@class="product-title"]/text()').extract()
        return self._clean_text(title[0]) if title else None

    @staticmethod
    def _parse_is_out_of_stock(response):
        return bool(response.xpath(
            '//body[contains(@class, "OutOfStockNoResultsNav")]'
        ))

    @staticmethod
    def _parse_reseller_id(url):
        reseller_id = re.search('pid=(\d+)', url, re.DOTALL)
        return reseller_id.group(1) if reseller_id else None

    @staticmethod
    def _parse_image_url(response):
        image_url = is_empty(response.xpath('//div[@class="product-photo"]'
                                            '//li[@class="product-photo--item"]'
                                            '//img/@src').extract())

        return urlparse.urljoin(response.url, image_url) if image_url else None

    @staticmethod
    def _parse_price(response):
        price = response.xpath('//*[contains(@class,"product-price--highlight")]/text()').extract()
        if not price:
            price = response.xpath('//*[@class="product-price"]/text()').extract()

        if price:
            if '-' in price[0]:
                price = price[0].split('-')
            return Price(
                price=price[0].replace(',', '').replace('$', '').strip(),
                priceCurrency="USD"
            )
        return None

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']

        buyer_review_values = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            review_json = json.loads(response.body)
            data = review_json["BatchedResults"]["q0"]["Results"][0]
            if data.get("Brand", None):
                product['brand'] = data["Brand"]["Name"]

            review_statistics = data['ReviewStatistics']

            if review_statistics.get("RatingDistribution", None):
                for item in review_statistics['RatingDistribution']:
                    key = str(item['RatingValue'])
                    buyer_review_values["rating_by_star"][key] = item['Count']

            if review_statistics.get("TotalReviewCount", None):
                buyer_review_values["num_of_reviews"] = review_statistics["TotalReviewCount"]

            if review_statistics.get("AverageOverallRating", None):
                buyer_review_values["average_rating"] = format(review_statistics["AverageOverallRating"], '.1f')
        except Exception as e:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
        finally:
            buyer_reviews = BuyerReviews(**buyer_review_values)
            product['buyer_reviews'] = buyer_reviews
            return product

    def _parse_variants(self, response):
        json_text = re.findall(r'gap.pageProductData = (.*?)};', response.body)
        variants_list = []

        if not json_text:
            return None
        json_text = json_text[0].decode('ascii', 'ignore') + "}"
        try:
            json_data = json.loads(json_text)
            if not json_data.get('variants', None):
                return None

            for datum in json_data['variants']:
                if not datum.get('productStyleColors', None):
                    continue
                variant_name = datum['name']
                for product_style_colors in datum['productStyleColors']:
                    for variant in product_style_colors:
                        color = variant['colorName']
                        image_url = variant['largeImagePath']
                        price = variant.get('localizedCurrentPrice')
                        if price:
                            price = float(price.replace(',', '').replace('$', '').strip())
                        for size in variant['sizes']:
                            variants_list.append({
                                'properties':{
                                    'variant_name': variant_name,
                                    'color': color,
                                    'size': size['sizeDimension1'],
                                },
                                'image_url': urlparse.urljoin(response.url, image_url),
                                'price': price,
                                'upc': size['upcCode'],
                                'sku': size['skuId'],
                                'in_stock': size['inStock']
                            })
            return variants_list
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
            return None

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t]", "", text).strip()

    def _scrape_product_links(self, response):
        try:
            json_data = json.loads(response.body)
            if json_data['productCategoryFacetedSearch']['productCategory'].get('childProducts', None):
                for product in json_data['productCategoryFacetedSearch']['productCategory']['childProducts']:
                    link = self.PRODUCT_URL.format(v_id=product['defaultSizeVariantId'],
                                                   p_id=product['businessCatalogItemId'])
                    yield link, SiteProductItem()
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)

    def _scrape_total_matches(self, response):
        try:
            json_data = json.loads(response.body)
            if json_data['productCategoryFacetedSearch'].get('totalItemCount', None):
                totals = json_data['productCategoryFacetedSearch']['totalItemCount']
                return int(totals)
            else:
                return 0
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)

    def _scrape_next_results_page_link(self, response):
        return None
