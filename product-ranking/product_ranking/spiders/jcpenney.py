# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import itertools
import json
import re
import string
import traceback
import urllib
import urlparse
import math

from scrapy import Selector
from scrapy.conf import settings
from scrapy.http import Request
from scrapy.log import INFO, WARNING

import spiders_shared_code
import spiders_shared_code.canonicalize_url
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import (BaseProductsSpider, FormatterWithDefaults,
                                     cond_set, cond_set_value)
from product_ranking.utils import extract_first
from product_ranking.validation import BaseValidator
from product_ranking.validators.jcpenney_validator import \
    JcpenneyValidatorSettings

is_empty = lambda x, y="": x[0] if x else y


class JcpenneyProductsSpider(BaseValidator, BaseProductsSpider):
    """ jcpenny.com product ranking spider.

    Takes `order` argument with following possible values:

    * `rating` (default)
    * `best`
    * `new`
    * `price_asc`, `price_desc`
    """

    name = 'jcpenney_products'

    settings = JcpenneyValidatorSettings

    allowed_domains = [
        'jcpenney.com',
        'jcpenney.ugc.bazaarvoice.com',
        'recs.richrelevance.com',
        'www.jcpenney.com',
        'm.jcpenney.com'
    ]

    SEARCH_URL = "https://www.jcpenney.com/s/{search_term}?Ntt={search_term}&page={page_num}"
    SORTING = None
    SORT_MODES = {
        'default': '',
        'best_match': '',
        'new arrivals': 'NA',
        'best_sellers': 'BS',
        'price_asc': 'PLH',
        'price_desc': 'PHL',
        'rating_desc': 'RHL'
    }

    REVIEW_URL = "http://jcpenney.ugc.bazaarvoice.com/1573redes2/{product_id}" \
                 "/reviews.djs?format=embeddedhtml"

    CATEGORIES_URL = "https://search-api.jcpenney.com/v1/j/breadcrumb?ppId={prod_id}"

    SEPHORA_REVIEW_URL = 'http://sephora.ugc.bazaarvoice.com/8723jcp/' \
                         '{product_id}/reviews.djs?format=embeddedhtml'

    MOBILE_VARIANTS_URL = "http://m.jcpenney.com/v4/products/{product_id}"

    VARIANTS_PRICE_URL = "http://m.jcpenney.com/v4/products/{product_id}/pricing/items"

    AVAILABILITY_URL = "http://m.jcpenney.com/v4/products/{product_id}/inventory"

    PRICING_CONTENT_URL = "https://browse-api.jcpenney.com/v1/product-aggregator/{product_id}/inventory/pricing"

    settings = JcpenneyValidatorSettings

    results_per_page = 24

    handle_httpstatus_list = [404]

    download_delay = 1

    def __init__(self, sort_mode=None, *args, **kwargs):
        retry_http_codes = settings.get('RETRY_HTTP_CODES')
        if 404 in retry_http_codes:
            retry_http_codes.remove(404)

        self.buyer_reviews = BuyerReviewsBazaarApi(called_class=self)
        if sort_mode:
            if sort_mode.lower() not in self.SORT_MODES:
                self.log('"%s" not in SORT_MODES')
            else:
                self.SORTING = self.SORT_MODES[sort_mode.lower()]

        super(JcpenneyProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(page_num=1),
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)
        settings.overrides['CONCURRENT_REQUESTS'] = 1
        self.user_agent = 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'

        self.current_page = 1

    def canonicalize_url(self, url):
        return spiders_shared_code.canonicalize_url.jcpenney(url)

    def start_requests(self):
        cookies = {'yoda-checkout-desktop': True,
                   'yoda-desktop': False}
        for request in super(JcpenneyProductsSpider, self).start_requests():
            request = request.replace(dont_filter=True, cookies=cookies)
            yield request

    def _parse_single_product(self, response):
        if response.status == 404:
            product = response.meta.get('product', SiteProductItem())
            product['url'] = response.url
            product['not_found'] = True
            product['no_longer_available'] = True
            product['response_code'] = 404
            return product
        return self.parse_product(response)

    @staticmethod
    def _is_sephora_reviews(response):
        return ('varisSephora=true'
                in response.body_as_unicode().replace(' ', '').replace("'", ''))

    @staticmethod
    def _is_not_found(response):
        return ("what you are looking for is currently unavailable" in response.body_as_unicode().lower()
                or "oops..." in response.body_as_unicode().lower())

    @staticmethod
    def _extract_reseller_id(response):
        reseller_id = is_empty(
            re.findall(
                r"ppId\s?=\s?\'(.+?)\';", response.body_as_unicode()
            ))
        if not reseller_id:
            reseller_id = extract_first(
                response.xpath('//span[@data-anid="productPPID"]/text()')
            )
        if not reseller_id:
            reseller_id = is_empty(re.findall(r"ppId=([^&]+)", response.url))
        if not reseller_id:
            reseller_id = is_empty(re.findall(r"(ppr?[^&?/]+)", response.url))
        if not reseller_id:
            reseller_id = is_empty(re.findall(r"(pp(\d+)?)", response.url))
        if not reseller_id:
            reseller_id = re.search('"productID":"(.*?)"', response.body)
            reseller_id = reseller_id.group(1) if reseller_id else None
        return reseller_id

    @staticmethod
    def _extract_model(response):
        model = "".join(response.xpath('//div[@data-automation-id="productModelNumber"]/*/text()').extract())
        model = re.search(r'#:(.+)', model)
        return model.group(1).strip() if model else None

    def parse_product(self, response):
        prod = response.meta['product']
        prod['url'] = response.url
        # prod['_subitem'] = True - implemented usual callback chain

        if self._is_not_found(response):
            prod['not_found'] = True
            prod['no_longer_available'] = True
            return prod

        product_id = self._extract_reseller_id(response)
        prod['reseller_id'] = product_id

        prod['model'] = self._extract_model(response)

        cond_set_value(prod, 'locale', 'en-US')
        self._populate_from_html(response, prod)

        review_id = is_empty(response.xpath(
            '//script/text()[contains(.,"reviewId")]'
        ).re(r'reviewId:\"(\d+)\",'))
        if not review_id:
            review_id = is_empty(response.xpath(
                '//script/text()[contains(.,"reviewIdNew")]'
            ).re(r'reviewId.*?\=.*?([a-zA-Z\d]+)'))
        if not review_id:
            review_id = re.search(r'id":"(\d+)","productId"', response.body_as_unicode())
            review_id = review_id.group(1) if review_id else None
        new_meta = {}
        new_meta['product'] = prod

        if self._is_sephora_reviews(response):
            review_url = self.url_formatter.format(
                self.SEPHORA_REVIEW_URL, product_id=review_id or product_id)
        else:
            review_url = self.url_formatter.format(
                self.REVIEW_URL, product_id=review_id or product_id)
        return Request(review_url, meta=new_meta,
                       callback=self._parse_reviews, dont_filter=True)

    def _populate_from_html(self, response, product):
        if 'title' in product and product['title'] == '':
            del product['title']
        # TODO fix this

        title = response.xpath('//h1[@aria-label="productTitle"]/text()').extract()
        if not title:
            title = response.xpath('//h1[@data-automation-id="product-title"]/text()').extract()
        if not title:
            title = response.xpath('//h1[@class="ProductTitle-productTitle"]/text()').extract()
            if not title:
                title = response.xpath('//h1[@itemprop="name"]/text()').extract()

        cond_set(product, 'title', title, conv=string.strip)

        image_url = is_empty(
            response.xpath(
                '//div[@class="Image-imageBoxMain"]/img[@class="Image-imageClass"]/@src'
            ).extract())

        if image_url:
            cond_set_value(
                product,
                'image_url',
                'http:' + image_url
            )

        oos = response.xpath('.//*[contains(@class, "GreenBold") and contains(text(), "Out of Stock")]')
        cond_set_value(product, 'is_out_of_stock', bool(oos))

        json_data = is_empty(
            response.xpath('//script').re(r'jcpPPJSON\s?=\s?({.*});'))

        if json_data:
            data = json.loads(json_data)
            brand = is_empty(is_empty(data['products'])['lots']).get('brandName', None)
            cond_set_value(
                product,
                'brand',
                brand
            )
        else:
            try:
                text = response.xpath(
                    '//script[@type="application/ld+json" and contains(text(), "brand")]/text()'
                ).re('"brand":(\{.+?\})')[0]
                data = json.loads(text)
                brand = data.get('name')
                cond_set_value(product, 'brand', brand)
            except:
                self.log('Can not extract brand value: {}'.format(traceback.format_exc()))

        search_price = response.meta.get('price')
        price = is_empty(response.xpath(
            '//span[@itemprop="price"]/a/text() |'
            '//span[@itemprop="price"]/text() |'
            '//span[@class="pp__price__value"]/text()'
        ).re(r"\d+.?\d{0,2}"))

        other_price = re.search('"productCurrentSellingPrice":"(.*?)"', response.body)

        # TODO fix properly?
        if not other_price:
            other_price = re.search('[\"\']min[\"\']\:([\d\.]+)\D[\"\']type[\"\']\:[\"\']SALE[\"\']', response.body)

        if not other_price:
            other_price = re.search('[\"\']min[\"\']\:([\d\.]+)\D[\"\']type[\"\']\:[\"\']original[\"\']', response.body)

        if price:
            product['price'] = Price(price=price, priceCurrency='USD')
        elif other_price:
            product['price'] = Price(price=other_price.group(1), priceCurrency='USD')
        elif search_price:
            product['price'] = Price(price=search_price, priceCurrency='USD')

    def _parse_reviews(self, response):
        product = response.meta['product']
        text = response.body_as_unicode().encode('utf-8')

        """ for debugging only!
        import requests
        text2 = requests.get('http://sephora.ugc.bazaarvoice.com/8723jcp/P261621/reviews.djs?format=embeddedhtml&page=0').text
        result = self.buyer_reviews.parse_buyer_reviews_per_page(response)
        open('/tmp/text', 'w').write(text)
        open('/tmp/text2', 'w').write(text2.encode('utf8'))
        import pdb; pdb.set_trace()
        """

        brs = self.buyer_reviews.parse_buyer_reviews_per_page(response)
        if brs.get('average_rating', None):
            if brs.get('rating_by_star', None):
                for k, v in brs['rating_by_star'].items():
                    if k not in ['1', '2', '3', '4', '5']:
                        # manually parse
                        arr = response.xpath(
                            '//span[contains(@class, "BVRRHistStarLabelText")]//span[contains(@class,"BVRRHistAbsLabel")]//text()').extract()
                        stars = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
                        for i in range(5):
                            num = arr[i * 2]
                            num = num.replace(',', '')
                            num = re.findall(r'\d+', num)[0]
                            stars[str(5 - i)] = int(num.replace(',', ''))
                        brs['rating_by_star'] = stars
                        break
                product['buyer_reviews'] = brs

        if not product.get('buyer_reviews', None) and response.status == 200:
            x = re.search(
                r"var materials=(.*),\sinitializers=", text, re.M + re.S)
            if x:
                jtext = x.group(1)
                jdata = json.loads(jtext)

                html = jdata['BVRRSourceID']
                sel = Selector(text=html)
                avrg = sel.xpath(
                    "//div[@id='BVRRRatingOverall_']"
                    "/div[@class='BVRRRatingNormalOutOf']"
                    "/span[contains(@class,'BVRRRatingNumber')]"
                    "/text()").extract()
                if not avrg:
                    avrg = sel.css('.BVRRNumber .BVRRRatingNumber ::text').extract()
                if avrg:
                    try:
                        avrg = float(avrg[0])
                    except ValueError:
                        avrg = 0.0
                else:
                    avrg = 0.0
                total = sel.xpath(
                    "//div[@class='BVRRHistogram']"
                    "/div[@class='BVRRHistogramTitle']"
                    "/span[contains(@class,'BVRRNonZeroCount')]"
                    "/span[@class='BVRRNumber']/text()").extract()
                if total:
                    try:
                        total = int(total[0].replace(',', ''))
                    except ValueError:
                        total = 0
                else:
                    total = 0
                hist = sel.xpath(
                    "//div[@class='BVRRHistogram']"
                    "/div[@class='BVRRHistogramContent']"
                    "/div[contains(@class,'BVRRHistogramBarRow')]")
                distribution = {}
                for ih in hist:
                    name = ih.xpath(
                        "span/span[@class='BVRRHistStarLabelText']"
                        "/text()").re(r"(\d) star")
                    try:
                        if name:
                            name = int(name[0])
                        value = ih.xpath(
                            "span[@class='BVRRHistAbsLabel']/text()").extract()
                        if value:
                            value = int(value[0])
                        distribution[name] = value
                    except ValueError:
                        pass
                if distribution:
                    dfr = dict({1: 0, 2: 0, 3: 0, 4: 0, 5: 0})
                    dfr.update(distribution)
                    reviews = BuyerReviews(total, avrg, dfr)
                    # reviews = ZERO_REVIEWS_VALUE.update(distribution)
                    product['buyer_reviews'] = reviews

        if 'buyer_reviews' not in product:
            cond_set_value(product, 'buyer_reviews', ZERO_REVIEWS_VALUE)

        product_id = product.get("reseller_id")
        if product_id:
            return Request(self.CATEGORIES_URL.format(prod_id=product_id),
                           callback=self._extract_categories_json,
                           meta=response.meta)
        else:
            return product

    def _extract_categories_json(self, response):
        product = response.meta['product']
        categories = []
        try:
            data = json.loads(response.body)
            categories_info = data.get('breadcrumbs', {})
            for category in categories_info:
                categories.append(category.get('breadCrumbLabel'))
        except:
            self.log('Error while parsing categories'.format(traceback.format_exc()), WARNING)
        if categories:
            cond_set_value(product, 'categories', categories[1:])
            cond_set_value(product, 'department', categories[-1])

        product_id = product.get('reseller_id')
        if product_id:
            return Request(self.AVAILABILITY_URL.format(product_id=product_id),
                           callback=self._extract_availability_json,
                           meta=response.meta)
        else:
            return product

    def _scrape_product_links(self, response):
        st = response.meta.get('search_term')
        body_links = response.xpath('//div[@class="productDisplay_image"]/a/@href').extract()
        try:
            json_links = re.search(r"jq.parseJSON\('(.+)'\);", response.body_as_unicode())
            json_links = json_links.group(1)
            json_links = json.loads(json_links.replace("\'", '\"'))
            json_links = json_links.get('organicZoneInfo').get('records')
            json_links = [link.get('pdpUrl') for link in json_links]
        except:
            json_links = []
        try:
            price_list = response.xpath("//script[@type='application/ld+json']/text()").extract()
            if len(price_list) > 1:
                price_list = json.loads(price_list[1])
            else:
                price_list = json.loads(price_list[0])
            price_list = [price.get('offers', {}).get('price') for price in price_list]
        except:
            price_list = []

        body_links.extend(json_links)
        for i, link in enumerate(body_links):
            try:
                price = float(price_list[i])
            except:
                price = None
            prod_item = SiteProductItem()
            req = Request(
                url=urlparse.urljoin(response.url, link),
                callback=self.parse_product,
                meta={
                    'product': prod_item,
                    'price': price,
                    'search_term': st,
                    'remaining': self.quantity
                },
                dont_filter=True
            )
            yield req, prod_item

    def _scrape_total_matches(self, response):
        try:
            total = response.xpath('//span[@data-anid="numberOfResults"]/text()').extract()

            if not total:
                total = re.findall('"totalProductsCount":(.*?),"', response.body)

            if total:
                total_matches = int(total[0].replace(',', ''))
            else:
                total_matches = 0
        except:
            self.log("Exception converting total_matches to int: {}".format(traceback.format_exc()))
            total_matches = 0
        return total_matches

    def _scrape_next_results_page_link(self, response):
        total_matches = self._scrape_total_matches(response)
        current_page = response.meta.get('current_page', 1)
        if current_page < math.ceil(total_matches / float(self.results_per_page)):
            current_page += 1
            response.meta['current_page'] = current_page
            next_page = Request(self.SEARCH_URL.format(
                page_num=current_page,
                search_term=urllib.quote_plus(
                    response.meta.get('search_term').encode('utf-8'))),
                meta=response.meta)
            return next_page

    @staticmethod
    def _build_properties_dict(product_json):
        properties = product_json.get('dimensions', [])
        properties_dict = {}
        for property in properties:
            options = property.get('options', [])
            name = property.get('name')
            for option in options:
                option_id = option.get('id')
                value = option.get('value')
                properties_dict[option_id] = {'name': name, 'value': value}
        return properties_dict

    def _extract_availability_json(self, response):
        try:
            data = json.loads(response.body_as_unicode())
        except:
            self.log('Can not convert into json: {}'.format(traceback.format_exc()))
            data = {}
        return self._build_availability_dict(data, response)

    def _build_availability_dict(self, availability_json, response):
        product = response.meta.get('product')
        product_id = product.get('reseller_id')
        availability_dict = {}
        for lot in availability_json:
            availability_dict[lot.get('id')] = lot.get('atp')
        new_meta = {'product': product, 'product_id': product_id,
                    'availability_dict': availability_dict}
        url = self.MOBILE_VARIANTS_URL.format(product_id=product_id)
        return Request(url, callback=self._parse_variants, meta=new_meta)

    @staticmethod
    def _build_variants(product_json, properties_dict, availability_dict):
        lots = product_json.get('lots', [])
        variants = []
        items = []

        for lot in lots:
            # collect all available variants
            items.extend(lot.get('items', []))

        for item in items:
            # make options hashable to use as keys in dict
            item.update(('options',
                         frozenset(v)) for k, v in item.iteritems() if k == 'options')

        item_by_options = dict(
            (d['options'], dict(d, index=index)) for (index, d) in enumerate(items)
        )

        properties = {}
        for k, v in properties_dict.iteritems():
            name = v.get('name')
            if name:
                properties.setdefault(name, []).append(k)

        for options in itertools.product(*properties.itervalues()):
            variant = {'properties': {}}
            item = item_by_options.get(frozenset(options))
            if item:
                sku_id = item.get('id')
                variant['in_stock'] = availability_dict.get(sku_id)
                variant['properties'] = {'sku': sku_id}
            else:
                variant['in_stock'] = False
                variant['is_out_of_stock'] = True
                variant['no_longer_available'] = True

            for option_id in options:
                option_data = properties_dict.get(option_id)
                option_name = option_data.get('name')
                option_value = option_data.get('value')
                variant['properties'][option_name] = option_value

            variants.append(variant)

        return variants

    def _parse_variants(self, response):
        product_id = response.meta.get('product_id')
        prod = response.meta.get('product')
        availability_dict = response.meta.get('availability_dict')
        try:
            product_json = json.loads(response.body_as_unicode(), strict=False)
            properties_dict = self._build_properties_dict(product_json)
            variants = self._build_variants(product_json, properties_dict, availability_dict)
            # Reformat variants properties for consistency, see BZ #9913 or CON-27755
            formatted_variants = self.transform_jcpenney_variants(variants)
            if formatted_variants:
                prod['variants'] = formatted_variants
        except:
            self.log('Can not convert body into json: {}'.format(traceback.format_exc()))
        url = self.VARIANTS_PRICE_URL.format(product_id=product_id)
        yield Request(url, callback=self._parse_variants_prices, meta=response.meta)

    @staticmethod
    def transform_jcpenney_variants(variants):
        if not variants:
            return variants

        for i, variant in enumerate(variants):
            properties = variant.get('properties', None)
            if 'lot' in variant and 'lot' not in properties:
                properties['lot'] = variant.pop('lot')
            if properties:
                # BZ case 2
                if 'waist' in properties:
                    # if (set(properties.keys()) - set(['lot']) - set(['color'])) == set(['waist']):
                    waist_value = properties.pop('waist')
                    properties['size'] = waist_value
                # BZ case 3
                if 'size' in properties and 'size range' in properties:
                    size_range_value = properties.pop('size range')
                    size_value = properties.pop('size')
                    properties['size'] = "{}/{}".format(size_range_value, size_value)
                else:
                    # BZ case 1
                    if 'inseam' in properties and 'length' not in properties:
                        inseam_value = properties.pop('inseam')
                        properties['length'] = inseam_value

            variants[i]['properties'] = properties
        return variants

    def _parse_variants_prices(self, response):
        prod = response.meta.get('product')
        variants = response.meta.get('product', {}).get('variants', [])
        prices = self._parse_prices_dict(response.body_as_unicode())
        for variant in variants:
            sku_id = variant.get('properties', {}).get('sku')
            variant['price'] = prices.get(sku_id)
        reseller_id = prod.get('reseller_id')
        price = prod.get('price')
        if reseller_id and not price:
            return Request(
                self.PRICING_CONTENT_URL.format(product_id=reseller_id),
                callback=self._parse_pricing_content,
                meta=response.meta
            )
        return prod

    def _parse_pricing_content(self, response):
        product = response.meta.get('product')
        price = None
        try:
            data = json.loads(response.body)
            price = data.get('analyticsPrice', {}).get('productCurrentSellingPrice')
        except:
            self.log("Error while parsing the json data for pricing".format(traceback.format_exc()))

        if price:
            product['price'] = Price(price=price, priceCurrency='USD')
        return product

    def _parse_prices_dict(self, body):
        prices = {}
        try:
            prices_json = json.loads(body, strict=False)
            variants = prices_json.get('data', [])
        except:
            self.log('Can not convert body into json: {}'.format(traceback.format_exc()))
            variants = []
        for variant in variants:
            # http://lewk.org/blog/python-dictionary-optimizations
            sku_id = str(variant.get('id'))
            price = min([price.get('min') for price in variant.get('amounts')])
            prices[sku_id] = price
        return prices
