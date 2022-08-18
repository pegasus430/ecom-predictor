# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback
from urlparse import urljoin

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults, cond_set_value
from product_ranking.guess_brand import guess_brand_from_first_words

from scrapy import Request
from scrapy.log import WARNING, DEBUG, INFO
from spiders_shared_code.gildanonline_variants import GildanOnlineVariants

class GildanOnlineProductsSpider(BaseProductsSpider):
    name = 'gildanonline_products'
    allowed_domains = ["gildan.com", "goldtoe.com"]

    PRODUCT_URL = "https://www.gildan.com/rest/model/atg/commerce/catalog/ProductCatalogActor/" \
                  "fullProductInfo?id={id}"

    SEARCH_URL = 'https://www.gildan.com/rest/model/atg/endeca/assembler/droplet/InvokeAssemblerActor/' \
                 'getContentItem?Ntt={search_term}&N=0&No={offset}&Nty=1&contentCollection=%2Fcontent%2FWebStoreSS%2F' \
                 'Shared%2FSearch&redirectPathCheck=%2Fcontent%2FWebStoreSS%2FShared%2FSearch%2FGO+' \
                 'Search+Results+Refinements+Settings'

    REVIEWS_URL = 'http://api.bazaarvoice.com/data/reviews.json' \
                  '?passkey=e5755922ss77539mmuya4uczr' \
                  '&apiversion=5.4' \
                  '&Include=Products' \
                  '&Stats=Reviews' \
                  '&Limit=1' \
                  '&Filter=ProductId:{product_id}'

    headers = {
        'Accept': 'text/html, application/xhtml+xml, image/jxr, */*',
        'Accept-Encoding': 'gzip, deflate, sdch, br',
        'Accept-Language': 'en-US,en;q=0.8',
        'Connection': 'keep-alive',
        'Host': 'www.gildan.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36 Edge/16.16299'
    }

    def __init__(self, *args, **kwargs):
        self.gr = GildanOnlineVariants()
        super(GildanOnlineProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(offset=0),
            site_name=self.allowed_domains[0],
            *args, **kwargs)

    def start_requests(self):
        for request in super(GildanOnlineProductsSpider, self).start_requests():
            if self.product_url:
                meta = request.meta.copy()
                meta['dont_redirect'] = True
                meta['handle_httpstatus_list'] = [302]
                request = request.replace(
                    headers=self.headers,
                    meta=meta
                )
            yield request

    def _parse_single_product(self, response):
        if response.status == 302:
            url = response.xpath('//a/@href').extract()[0]
            headers = self.headers.copy()
            headers['Host'] = 'www.goldtoe.com'
            return response.request.replace(headers=headers, url=url)
        id = re.search(r"pdp\?pid=(.*?)';", response.body)
        if id:
            url = self.PRODUCT_URL.format(id=id.group(1))
            return response.request.replace(url=url, callback=self.parse_product)
        else:
            self.log('Can not get the product id')

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        product['locale'] = 'en_US'

        try:
            data = json.loads(response.body_as_unicode())
        except:
            self.log("Error while parsing json data: {}".format(traceback.format_exc()), WARNING)
            return product

        product['title'] = data.get('product', {}).get('displayName')
        product['brand'] = guess_brand_from_first_words(product['title']) if product['title'] else None
        product['department'] = data.get('product', {}).get('parentCategories')[0].get('displayName', {})
        product['image_url'] = urljoin('https://www.gildan.com/assets/img/catalog/product/small/',
                                                data.get('product', {}).get('mainImage')) if data.get('product', {}).get('mainImage') else None

        price = data.get('product', {}).get('pricePair', {}).get('salePrice')
        if not price:
            price = data.get('product', {}).get('pricePair', {}).get('listPrice')
        product['price'] = Price(price=price, priceCurrency='USD') if price else None

        was_now = self._parse_was_now(data.get('product', {}).get('pricePair', {}))
        cond_set_value(product, 'was_now', was_now)

        cond_set_value(product, 'promotions', bool(was_now))

        product['url'] = data.get('product', {}).get('fullUrl')

        variants = self._parse_variants(data.get('skus'))
        cond_set_value(product, 'variants', variants)

        product_id = data.get('product', {}).get('repositoryId')
        if product_id:
            return Request(self.REVIEWS_URL.format(product_id=product_id),
                          callback=self._parse_buyer_reviews,
                          meta=response.meta,
                          dont_filter=True)

        return product

    @staticmethod
    def _parse_was_now(price_info):
        if price_info.get('salePrice') and price_info.get('listPrice'):
            return ', '.join([str(price_info.get('salePrice')), str(price_info.get('listPrice'))])

    def _parse_variants(self, skus):
        self.gr.setupSC(skus)
        return self.gr._variants()

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']
        try:
            data = json.loads(response.body)
            product_data = data.get('Includes', {}).get('Products', {})
            if product_data:
                review_statistics = product_data.values()[0].get('ReviewStatistics') if product_data.values() else None

                if review_statistics:
                    cond_set_value(product, 'buyer_reviews', BuyerReviews(
                        num_of_reviews=review_statistics.get('TotalReviewCount', 0),
                        average_rating=round(review_statistics.get('AverageOverallRating', 0), 1),
                        rating_by_star=dict(map(lambda x: (str(x['RatingValue']), x['Count']),
                                                review_statistics.get('RatingDistribution')))
                    ))
        except:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()), WARNING)

        return product

    def _scrape_total_matches(self, response):
        total_matches = 0

        try:
            data = json.loads(response.body)
        except:
            self.log("Exception looking for total_matches {}".format(traceback.format_exc()), DEBUG)
        else:
            contents = data.get('contentItem', {}).get('contents', [])
            for content in contents:
                sections = content.get('sections', [])
                for section in sections:
                    if section.get('@type') == 'VSG-Widget-ResultsList':
                        return section.get('totalNumRecs')

        return total_matches

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body)
        except:
            self.log("Found no product links in {url}".format(url=response.url), INFO)
        else:
            contents = data.get('contentItem', {}).get('contents', [])
            links = []
            for content in contents:
                sections = content.get('sections', [])
                for section in sections:
                    if section.get('@type') == 'VSG-Widget-ResultsList':
                        links += section.get('records', [])

            ids = [
                link.get('attributes', {}).get('product.repositoryId', [])[0]
                for link in links
                if len(link.get('attributes', {}).get('product.repositoryId', [])) > 0
                ]
            for id in ids:
                url = self.PRODUCT_URL.format(id=id)
                yield url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        total_matches = meta.get('total_matches', 0)
        results_per_page = meta.get('results_per_page')
        page_num = meta.get('page_num', 1)
        if not results_per_page:
            results_per_page = 12
        if total_matches and results_per_page and page_num * results_per_page < total_matches:
            next_link = self.SEARCH_URL.format(search_term=meta['search_term'],
                                               offset=page_num*results_per_page)
            meta['page_num'] = page_num + 1
            return Request(
                url=next_link,
                meta=meta,
                dont_filter=True
            )

    def _get_products(self, response):
        for req in super(GildanOnlineProductsSpider, self)._get_products(response):
            yield req.replace(dont_filter=True)
