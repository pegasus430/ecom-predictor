# -*- coding: utf-8 -*-
import re
import json
import traceback
from urlparse import urljoin

from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults
from spiders_shared_code.sephora_variants import SephoraVariants

from scrapy import Request


class SephoraProductsSpider(BaseProductsSpider):
    name = 'sephora_products'
    allowed_domains = ['sephora.com']
    SEARCH_URL = "https://www.sephora.com/search/search.jsp?keyword={search_term}&mode=partial&currentPage={page_num}"
    REVIEW_URL = "https://api.bazaarvoice.com/data/reviews.json?Filter=ProductId%3A{product_id}&Sort=Helpfulness%3Adesc&Limit=30&Offset=0&Include=Products%2CComments&Stats=Reviews&passkey=rwbw526r2e7spptqd2qzbkp7&apiversion=5.4"

    def __init__(self, *args, **kwargs):
        url_formatter = FormatterWithDefaults(page_num=1)
        self.sv = SephoraVariants()
        super(SephoraProductsSpider, self).__init__(
            url_formatter=url_formatter,
            *args,
            **kwargs
        )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta.get('product', SiteProductItem())

        try:
            product_json = response.xpath('//script[@id="linkJSON"]/text()').extract()
            product_json = json.loads(product_json[0])
            is_product = False
            for datum in product_json:
                if 'currentProduct' in datum.get('props', {}):
                    product_json = datum.get('props', {}).get('currentProduct', {})
                    self.sv.setupCH(product_json)
                    is_product = True
                    break
            if not is_product:
                self.log('Product not found')
                return product

        except:
            self.log('Error Parsing Product Json: {}'.format(traceback.format_exc()))
            return product

        title = self._parse_title(product_json)
        cond_set_value(product, 'title', title)

        price = self._parse_price(product_json)
        cond_set_value(product, 'price', price)

        image_url = self._parse_image(product_json)
        cond_set_value(product, 'image_url', image_url)

        brand = self._parse_brand(product_json)
        cond_set_value(product, 'brand', brand)

        sku = self._parse_sku(product_json)
        cond_set_value(product, 'sku', sku)

        categories = self._parse_categories(product_json)
        cond_set_value(product, 'categories', categories)

        if categories:
            department = categories[-1]
            cond_set_value(product, 'department', department)

        is_out_of_stock = self._parse_out_of_stock(product_json)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        variants = self._parse_variants()
        cond_set_value(product, 'variants', variants)

        product['locale'] = "en-US"

        avg_review = product_json.get('rating')
        num_of_reviews = product_json.get('reviews')
        num_of_reviews = int(num_of_reviews) if num_of_reviews else None
        product_id = re.search(r'P(\d+)', response.url)

        if num_of_reviews and product_id:
            product_id = product_id.group(0)
            product['buyer_reviews'] = {
                'num_of_reviews': num_of_reviews,
                'average_rating': float(avg_review) if avg_review else 0.0,
                'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
            }
            meta = response.meta.copy()
            meta['product'] = product
            meta['product_id'] = product_id
            url = self.REVIEW_URL.format(product_id=product_id)
            return Request(url=url,
                           callback=self._parse_reviews,
                           meta=meta,
                           dont_filter=True)

        return product

    def _parse_reviews(self, response):
        product = response.meta['product']
        product_id = response.meta['product_id']
        rating_by_star = product['buyer_reviews']['rating_by_star']
        try:
            reviews = json.loads(response.body)
            for review in reviews.get('Includes', {}).get('Products', {}).get(product_id, {}).get('ReviewStatistics',{}).get('RatingDistribution', []):
                rating_by_star[str(review.get('RatingValue'))] = review.get('Count')
        except:
            self.log('Error Parsing Product review: {}'.format(traceback.format_exc()))
            return product

        product['buyer_reviews']['rating_by_star'] = rating_by_star
        return product

    @staticmethod
    def _parse_title(product_json):
        title = product_json.get('displayName')
        return title

    def _parse_price(self, product_json):
        price = product_json.get('currentSku', {}).get('listPrice')
        try:
            return Price(price=float(price[1:].replace(',', '')), priceCurrency='USD') if price else None
        except:
            self.log('Error Parsing Price: {}'.format(traceback.format_exc()))

    @staticmethod
    def _parse_image(product_json):
        image_url = product_json.get('currentSku', {}).get('skuImages', {}).get('image1500')
        return ('https://www.sephora.com' + image_url) if image_url else None

    @staticmethod
    def _parse_brand(product_json):
        return product_json.get('brand', {}).get('displayName')

    @staticmethod
    def _parse_sku(product_json):
        return product_json.get('currentSku', {}).get('skuId')

    @staticmethod
    def _parse_categories(product_json):
        categories = product_json.get('breadcrumbsSeoJsonLd')
        return re.findall('"name\\\":\\\"(.*?)\\\"', categories) if categories else None

    @staticmethod
    def _parse_out_of_stock(product_json):
        return product_json.get('currentSku', {}).get('isOutOfStock')

    def _parse_variants(self):
        return self.sv._variants()

    def _scrape_total_matches(self, response):
        total_matches = re.search('"PRODUCTS","total_items":(\d+)}', response.body, re.DOTALL)
        return int(total_matches.group(1)) if total_matches else None

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        current_page = meta.get('current_page', 1)
        total_matches = meta.get('total_matches', 0)
        if current_page * 60 > total_matches:
            return
        current_page += 1
        st = response.meta['search_term']
        url = self.SEARCH_URL.format(page_num=current_page, search_term=st)
        meta['current_page'] = current_page
        return Request(
            url,
            meta=meta,)

    def _scrape_product_links(self, response):
        links = re.findall('"product_url":"(.*?)"', response.body)
        for link in links:
            link = urljoin(response.url, link)
            yield link, SiteProductItem()
