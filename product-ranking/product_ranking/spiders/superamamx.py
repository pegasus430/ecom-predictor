# -*- coding: utf-8 -*-#

import json
import re
import traceback

from scrapy.log import WARNING
from scrapy.http import Request
from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value

class SuperamaMxProductSpider(BaseProductsSpider):
    name = 'superamamx_products'
    allowed_domains = ["www.superama.com.mx"]

    REVIEW_URL = 'https://api.bazaarvoice.com/data/batch.json?' \
                 'passkey=ca00NLtrMkSnTddOCbktCnskwSV7OaQHCOTa3EZNMR2KE' \
                 '&apiversion=5.5' \
                 '&displaycode=19472-es_mx' \
                 '&resource.q0=products' \
                 '&filter.q0=id%3Aeq%3A{product_id}' \
                 '&stats.q0=questions%2Creviews' \
                 '&filteredstats.q0=questions%2Creviews' \
                 '&filter_questions.q0=contentlocale%3Aeq%3Aes_MX' \
                 '&filter_answers.q0=contentlocale%3Aeq%3Aes_MX' \
                 '&filter_reviews.q0=contentlocale%3Aeq%3Aes_MX' \
                 '&filter_reviewcomments.q0=contentlocale%3Aeq%3Aes_MX'

    SEARCH_URL = 'https://www.superama.com.mx/buscador/resultado?' \
                     'busqueda={search_term}' \
                 '&departamento=' \
                 '&familia=' \
                 '&linea='

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        meta = response.meta
        product = meta['product']

        # Set locale
        product['locale'] = 'es-ES'

        try:
            product_json = re.findall(r'var model = (.*?)};', response.body)
            product_json = json.loads(product_json[0] + '}')
        except:
            self.log('Error Parsing Product Json: {}'.format(traceback.format_exc()))
            return product

        # Parse title
        title = self.parse_title(product_json)
        cond_set_value(product, 'title', title)

        # Parse brand
        brand = self.parse_brand(product_json)
        cond_set_value(product, 'brand', brand)

        # Parse price
        price = self.parse_price(response, product_json)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self.parse_image_url(product_json)
        cond_set_value(product, 'image_url', image_url)

        # Parse description
        description = self.parse_description(product_json)
        cond_set_value(product, 'description', description)

        # Parse stock status
        is_out_of_stock = self.parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        categories = self.parse_categories(response)
        cond_set_value(product, 'categories', categories)

        if categories:
            department = categories[-1]
            cond_set_value(product, 'department', department)

        upc = self.parse_upc(product_json)
        cond_set_value(product, 'upc', upc)

        if upc:
            url = self.REVIEW_URL.format(product_id=upc)
            return Request(
                url=url,
                callback=self.parse_buyer_reviews,
                meta={'product': product},
                dont_filter=True
            )

        return product

    @staticmethod
    def parse_title(product_json):
        return product_json.get('Description')

    @staticmethod
    def parse_brand(product_json):
        return product_json.get('Brand')

    def parse_price(self, response, product_json):
        price_json = response.xpath('//script[@type="application/ld+json"]/text()').extract()
        price_currency = 'MXN'
        try:
            price_json = json.loads(price_json[0])
            price = price_json.get('offers', {}).get('price')
            price_currency = price_json.get('offers', {}).get('priceCurrency', 'MXN')
        except:
            self.log('Parsing Error Price JSON: {}'.format(traceback.format_exc()))
            price = product_json.get('Price')
        finally:
            return Price(price=price, priceCurrency=price_currency) if price else None

    @staticmethod
    def parse_image_url(product_json):
        image = product_json.get('UrlImagenes', [])
        return 'https://www.superama.com.mx/Content/' + image[0] if image else None

    @staticmethod
    def parse_description(product_json):
        return product_json.get('Details')

    def parse_is_out_of_stock(self, response):
        price_json = response.xpath('//script[@type="application/ld+json"]/text()').extract()
        try:
            price_json = json.loads(price_json[0])
            return price_json.get('offers', {}).get('availability') != 'http://schema.org/InStock'
        except:
            self.log('Parsing Error Price JSON: {}'.format(traceback.format_exc()))
        return False

    @staticmethod
    def parse_categories(response):
        categories = response.xpath('//ol[@class="breadcrumb"]/li/a/text()').extract()
        return categories if categories else None

    @staticmethod
    def parse_upc(product_json):
        return product_json.get('Upc')

    def parse_buyer_reviews(self, response):
        product = response.meta['product']

        buyer_review_values = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            review_json = json.loads(response.body)
            review_statistics = review_json["BatchedResults"]["q0"]["Results"][0]['ReviewStatistics']

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

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t\r]", "", text).strip()

    def _scrape_total_matches(self, response):
        try:
            search_json = json.loads(response.body)
            products = search_json.get('Products', [])
            return len(products)
        except:
            self.log('Error Parsing Search Term: {}'.format(traceback.format_exc()))

    def _scrape_product_links(self, response):
        try:
            search_json = json.loads(response.body)
            products = search_json.get('Products', [])
            for product in products:
                url = 'https://www.superama.com.mx/catalogo/'
                url += product.get('SeoDepartamentoUrlName') + '/' \
                    if product.get('SeoDepartamentoUrlName') \
                    else ''
                url += product.get('SeoFamiliaUrlName') + '/' \
                    if product.get('SeoFamiliaUrlName') \
                    else ''
                url += product.get('SeoLineaUrlName') + '/' \
                    if product.get('SeoLineaUrlName') \
                    else ''
                url += product.get('SeoProductUrlName') + '/' \
                    if product.get('SeoProductUrlName') \
                    else ''
                url += product.get('Upc') if product.get('Upc') else None
                yield url, SiteProductItem()
        except:
            self.log('Error Parsing Search Term: {}'.format(traceback.format_exc()))

    def _scrape_next_results_page_link(self, response):
        pass