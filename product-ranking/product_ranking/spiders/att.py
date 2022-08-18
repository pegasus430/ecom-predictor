# -*- coding: utf-8 -*-

# TODO:
# image url
# zip code "in stock" check
#

from __future__ import division, absolute_import, unicode_literals

import json
import re
import itertools
import os
import copy
import traceback
import math

from scrapy import Request
from scrapy.dupefilter import RFPDupeFilter
from scrapy.conf import settings

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.spiders import BaseProductsSpider, cond_set, cond_set_value


class CustomHashtagFilter(RFPDupeFilter):
    """ Considers hashtags to be a unique part of URL """

    @staticmethod
    def rreplace(s, old, new, occurrence):
        li = s.rsplit(old, occurrence)
        return new.join(li)

    def _get_unique_url(self, url):
        return self.rreplace(url, '#', '_', 1)

    def request_seen(self, request):
        fp = self._get_unique_url(request.url)
        if fp in self.fingerprints:
            return True
        self.fingerprints.add(fp)
        if self.file:
            self.file.write(fp + os.linesep)


class ATTProductsSpider(BaseProductsSpider):
    name = "att_products"
    allowed_domains = ['att.com',
                       'api.bazaarvoice.com',
                       'recs.richrelevance.com']

    SEARCH_URL = "https://www.att.com/global-search/search?q={search_term}"
    SEARCH_API_URL = "https://www.att.com/global-search/query/?rows=20&start={start_number}&q={search_term}" \
                     "&smb=false&catField=Shop"

    VARIANTS_ANGULAR_URL = "https://www.att.com/services/shopwireless/model/att/ecom/api/" \
                           "DeviceDetailsActor/getDeviceProductDetails?" \
                           "includeAssociatedProducts=true&includePrices=true&skuId={sku}"

    BUYER_REVIEWS_URL = "https://api.bazaarvoice.com/data/batch.json?passkey={pass_key}" \
                        "&apiversion=5.5&displaycode=4773-en_us&resource.q0=products" \
                        "&filter.q0=id%3Aeq%3A{sku}&stats.q0=reviews"

    BUYER_REVIEWS_PASS = '9v8vw9jrx3krjtkp26homrdl8'

    def __init__(self, *args, **kwargs):
        settings.overrides['USE_PROXIES'] = True
        settings.overrides['DOWNLOAD_DELAY'] = 1

        self.TWOCAPTCHA_APIKEY = settings.get('TWOCAPTCHA_APIKEY')
        self.user_agent = 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'

        self.br = BuyerReviewsBazaarApi(called_class=self)

        super(ATTProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')

        middlewares['product_ranking.custom_middlewares.ReCaptchaV1Middleware'] = 500
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        if not self.searchterms:
            for request in super(ATTProductsSpider, self).start_requests():
                request = request.replace(dont_filter=True)
                yield request

        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_API_URL,
                    search_term=st,
                    start_number=0
                ),
                dont_filter=True,
                meta={
                    'search_term': st,
                    'remaining': self.quantity
                }
            )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    @staticmethod
    def _parse_items(response):
        items = response.xpath("//ol[@class='text-legal']//li")
        return items

    def _get_sku(self, response):
        sku = response.meta.get('sku')
        if not sku:
            sku = re.search('sku=(.*)', self.product_url)
            if sku:
                sku = sku.group(1).strip()
        return sku

    def _parse_title(self, response):
        title = None
        items = self._parse_items(response)
        for item in items:
            if 'Item name' in item.extract():
                title = item.xpath(".//span/text()").extract()
                break

        return title[0] if title else None

    @staticmethod
    def _parse_ajax_variants(variants):
        result_variants = []
        v = variants
        variant = copy.copy({})
        variant['in_stock'] = not v.get('outOfStock', None)
        # get the lowest price
        price_list_options = v.get('priceList', [])
        price_list_options = sorted(price_list_options, key=lambda val: val.get('listPrice', 0))
        variant['price'] = price_list_options[0].get('listPrice', None)
        variant['sku'] = v.get('skuId', None)
        variant['selected'] = v.get('selectedSku', False)
        props = copy.copy({})
        if v.get('color', None):
            props['color'] = v['color']
        if v.get('size', None):
            props['size'] = v['size']
        variant['properties'] = props
        result_variants.append(variant)
        return result_variants

    def _get_brs_type_for_this_product(self, brs_sku, response):
        brs_types = ['FilteredReviewStatistics', 'ReviewStatistics']
        prod = response.meta['product']
        num_of_reviews_ = response.meta.get('num_of_reviews_', None)
        if not num_of_reviews_:
            return brs_types[0]  # fall back to this type
        total_reviews_filt = brs_sku[brs_types[0]]['TotalReviewCount']
        total_reviews_unfilt = brs_sku[brs_types[1]]['TotalReviewCount']
        # find the number which is closer to the on-page scraped one
        if abs(num_of_reviews_ - total_reviews_filt) \
                < (num_of_reviews_ - total_reviews_unfilt):
            return brs_types[0]
        else:
            return brs_types[1]

    def _on_buyer_reviews_response(self, response):
        product = response.meta['product']
        try:
            raw_json = json.loads(response.body_as_unicode())
        except Exception as e:
            self.log('Invalid reviews: {}'.format(str(e)))
            return product
        buyer_reviews_data = raw_json.get('BatchedResults', {}).get('q0', {})
        response = response.replace(body=json.dumps(buyer_reviews_data))
        buyer_reviews = BuyerReviews(
            **self.br.parse_buyer_reviews_products_json(response))
        product['buyer_reviews'] = buyer_reviews

        return product

    def _parse_ajax_product_data(self, response):
        prod = response.meta['product']
        sku = prod.get('sku')
        try:
            v = json.loads(response.body).get('result').get('methodReturnValue', {}).get('skuItems', {}).get(sku, {})
            is_oos = v.get('outOfStock')
            if is_oos:
                if '{{' in prod.get('title'):
                    prod['title'] = response.meta['title_no_sku']
                    prod['is_out_of_stock'] = True
                    prod['sku'] = response.meta['selected_sku']
                    return prod

            prod['variants'] = self._parse_ajax_variants(v)
            prod['is_out_of_stock'] = v['outOfStock']
            prod['model'] = v.get('model', '')
            # get the lowest price
            price_list_options = v.get('priceList', [])
            price_list_options = sorted(price_list_options, key=lambda val: val.get('listPrice', 0))
            _price = price_list_options[0].get('listPrice', None)
            if _price or _price == 0:
                prod['price'] = Price(price=_price, priceCurrency='USD')
            if v.get('retailAvailable', None) is False:
                prod['available_store'] = 0
            prod['title'] = v['displayName']
            prod['sku'] = response.meta['selected_sku']
            prod['reseller_id'] = prod.get('sku')
        except:
            self.log('Error whild parsing Json data{}'.format(traceback.format_exc()))

        new_meta = response.meta
        new_meta['product'] = prod
        if sku:
            return Request(
                self.BUYER_REVIEWS_URL.format(pass_key=self.BUYER_REVIEWS_PASS,
                                              sku=sku),
                callback=self._on_buyer_reviews_response,
                meta=new_meta,
                dont_filter=True
            )
        return prod

    def _on_variants_response_url2(self, response):
        variants = []
        prod = response.meta['product']
        variants_block = response.css('#pbDeviceVariants')
        if variants_block:
            colors = variants_block.css('#variantColor #colorInput a')
            sizes = variants_block.css('#variantSize #sizeInput a')
            if colors:
                colors = [c.xpath('./@title').extract()[0] for c in colors]
                colors = [{'color': c} for c in colors]
            if sizes:
                sizes = [s.xpath('./text()').extract()[0].strip() for s in sizes]
                sizes = [{'size': s} for s in sizes]
            if colors and sizes:
                variants_combinations = list(itertools.product(sizes, colors))
            elif colors:
                variants_combinations = colors
            else:
                variants_combinations = sizes
            for variant_combo in variants_combinations:
                new_variant = copy.copy({})
                new_variant['properties'] = variant_combo
                variants.append(new_variant)
            prod['variants'] = variants
        if u'available online - web only' in response.body_as_unicode().lower():
            prod['available_store'] = 0
        return prod

    def parse_product(self, response):
        product = response.meta['product']
        product['_subitem'] = True
        product['title'] = self._parse_title(response)
        if product['title']:
            # this needed only for att.com, mostly for headsets
            split_title = product['title'].split(' - ') if ' - ' in product['title'] else None
            if split_title:
                split_title = [s.strip() for s in split_title if s.strip()]
                brand_list = []
                for section in split_title:
                    brand_list.append(guess_brand_from_first_words(section))
                brand_list = [b for b in brand_list if b]
                product['brand'] = brand_list[0] if brand_list else None
            else:
                product['brand'] = guess_brand_from_first_words(product['title'])
        cond_set(
            product, 'image_url',
            response.xpath('//meta[contains(@name,"og:image")]/@content').extract())
        cond_set(
            product, 'image_url',
            response.xpath('//meta[contains(@property,"og:image")]/@content').extract())
        if not product.get('image_url', None):
            cond_set(
                product, 'image_url',
                response.xpath('//img[contains(@id,"deviceHeroImage")]/@src').extract())

        sku = self._get_sku(response)
        cond_set_value(product, 'sku', sku)

        new_meta = response.meta
        new_meta['product'] = product
        new_meta['selected_sku'] = self._get_sku(response)
        # response.xpath does not work here for some reasons
        num_of_reviews_ = re.search('<meta itemprop="reviewCount" content="(\d+)"',
                                    response.body_as_unicode())
        if num_of_reviews_:
            new_meta['num_of_reviews_'] = int(num_of_reviews_.group(1))

        if not product.get('title', None):
            return

        if '{{' in product['title']:
            # we got a bloody AngularJS-driven page, parse it
            for title_no_sku in response.xpath(
                    '//h1[contains(@ng-if,"(!selectedSku.preOwned")]/text()').extract():
                if not '{{' in title_no_sku:
                    new_meta['title_no_sku'] = title_no_sku

        if sku:
            return Request(
                self.VARIANTS_ANGULAR_URL.format(sku=self._get_sku(response)),
                callback=self._parse_ajax_product_data,
                dont_filter=True,
                meta=new_meta)
        return product

    def _scrape_product_links(self, response):
        st = response.meta.get('search_term')
        try:
            data = json.loads(response.body)
            prods = data.get('result', {}).get('response', {}).get('docs', [])
        except Exception:
            self.log(
                "Failed parsing json at {} - {}".format(traceback.format_exc()))
            prods = []

        for prod in prods:
            link = prod.get('productURL')
            if not link:
                link = prod.get('url_learnMorePage_en')
                link = link[0] if link else None
            if not link:
                continue
            prod_item = SiteProductItem()
            req = Request(
                link,
                callback=self.parse_product,
                meta={
                    "product": prod_item,
                    'search_term': st,
                    'remaining': self.quantity,
                    'sku': prod.get('id')
                },
                dont_filter=True,
            )
            yield req, prod_item

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        current_page = meta.get('current_page', 1)
        total_matches = response.meta.get('total_matches')
        st = response.meta.get('search_term')
        start_number = current_page * 20
        results_per_page = self._scrape_results_per_page(response)
        if not results_per_page:
            results_per_page = 20
        if total_matches and (current_page < math.ceil(total_matches / float(results_per_page))):
            current_page += 1
            next_link = self.SEARCH_API_URL.format(
                search_term=st,
                start_number=start_number)
            meta['current_page'] = current_page
            return Request(
                next_link,
                meta=meta,
                dont_filter=True
            )

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body)
            total_matches = data.get('result', {}).get('response', {}).get('numFound')
            return int(total_matches)
        except:
            self.log(
                "Failed parsing total matches".format(traceback.format_exc()))
            return
