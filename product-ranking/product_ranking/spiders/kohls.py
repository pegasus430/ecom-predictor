# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import json
import re
import urllib
import traceback

from scrapy import Selector
from scrapy.http import Request
from scrapy.log import ERROR, WARNING
from scrapy.conf import settings

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import (BaseProductsSpider, FormatterWithDefaults,
                                     _extract_open_graph_metadata, cond_set,
                                     cond_set_value, populate_from_open_graph,
                                     FLOATING_POINT_RGEX)
from product_ranking.utils import is_empty
from product_ranking.validation import BaseValidator
from spiders_shared_code.kohls_variants import KohlsVariants


class KohlsProductsSpider(BaseValidator, BaseProductsSpider):
    """ kohls.com product ranking spider.

    `upc` field is missing

    Takes `order` argument with following possible values:

    * `rating` (default)
    * `best`
    * `new`
    * `price_asc`, `price_desc`
    """

    name = 'kohls_products'
    allowed_domains = [
        'kohls.com',
        'kohls.ugc.bazaarvoice.com',
        'hlserve.com'
    ]

    SEARCH_URL = "https://www.kohls.com/search.jsp?N=0&search={search_term}&" \
                 "submit-search=web-regular&S={sort_mode}&PPP=60&WS={start}&exp=c"

    SEARCH_URL_AJAX = "https://www.kohls.com/search.jsp?" \
                      "N=0&search={search_term}&PPP=60&WS=0&srp=e2&ajax=true&gNav=false"

    SPONSORED_API = "https://www.hlserve.com/delivery/api/search?keyword=jeans" \
                    "&hlpt=S&pgsize=60&pgn={current_page}&pcount=60&sort=Featured&" \
                    "view=grid&usestate=1&platform=web&_=19133725709&" \
                    "~uid=6e307345-4dcd-43cc-aa9f-8d627286a9d8&abe=0&" \
                    "puserid=%5BCS%5Dv1%7C2D3C61350503098F-400011988000AB08%5BCE%5D&" \
                    "minmes=1&maxmes=12&minorganic=3&creative=182x2464_T-R-IG_TI_1-8_RightColumn&" \
                    "beacon=individual&filters=%7B%22ratingeligible%22%3A%221%22%7D&" \
                    "required_filters=ratingeligible&" \
                    "pgnflbk=0&abbucket=A&~it=js&" \
                    "organicskus={sku_list}&" \
                    "apiKey={api_key}"

    SORTING = None

    SORT_MODES = {
        'default': '1',
        'featured': '1',
        'new': '2',
        'best_sellers': '3',
        'price_asc': '4',
        'price_desc': '5',
        'highest_rated': '6'
    }

    REVIEW_URL = "http://kohls.ugc.bazaarvoice.com/9025" \
                 "/{product_id}/reviews.djs?format=embeddedhtml"

    handle_httpstatus_list = [404]

    def __init__(self, sort_mode=None, *args, **kwargs):
        self.start_pos = 0
        self.per_page = 24
        if sort_mode:
            if sort_mode.lower() not in self.SORT_MODES:
                self.log('"%s" not in SORT_MODES')
            else:
                self.SORTING = self.SORT_MODES[sort_mode.lower()]
        super(KohlsProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                sort_mode=self.SORTING or self.SORT_MODES['default']),
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)
        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36"
        # settings.overrides['USER_AGENT'] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36'
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        settings.overrides['USE_PROXIES'] = True

    def start_requests(self):
        for st in self.searchterms:
            url = self.url_formatter.format(
                self.SEARCH_URL,
                search_term=urllib.quote_plus(st.encode('utf-8')),
                start=0,
                sort_mode=self.SORTING or ''
            )
            yield Request(
                url,
                meta={'search_term': st, 'remaining': self.quantity},
                callback=self._help_search
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            yield Request(
                self.product_url, self._parse_single_product,
                dont_filter=True, meta={
                    'product': prod,
                    'handle_httpstatus_list': self.handle_httpstatus_list}
            )

    def _help_search(self, response):
        if self._check_search_error(response):
            if self.not_a_product(response):
                remaining = response.meta['remaining']
                search_term = response.meta['search_term']

                self.log("For search term '%s' with %d items remaining,"
                         " failed to retrieve search page: %s"
                         % (search_term, remaining, response.request.url),
                         WARNING)
            else:
                prod = SiteProductItem()
                prod['is_single_result'] = True
                prod['url'] = response.url
                prod['search_term'] = response.meta['search_term']
                response.meta['product'] = prod

                return self._parse_single_product(response)
        else:
            try:
                sku_list = re.search(r'("productIdMap"|"rrProductIdMap"):(\[.*?\]),', response.body_as_unicode(), re.DOTALL).group(2)
                sku_list = json.loads(sku_list)
                sku_list = '|'.join(sku_list)
            except:
                self.log('Error Parsing Sku List:{}'.format(traceback.format_exc()))
                return self.parse(response)
            prods = list(self._get_product_links(response))
            if not prods:
                return self.parse(response)

            current_page = response.meta.get('current_page', 1)
            prod_requests = response.meta.get('prod_requests', {})
            if not response.meta.get('total_matches'):
                response.meta['total_matches'] = self._scrape_total_matches(response)

            prod_requests[current_page] = prods
            response.meta['prod_requests'] = prod_requests

            api_key = re.search(r'apiKey=(.*?)",', response.body_as_unicode())
            api_key = api_key.group(1).upper() if api_key else response.meta.get('api_key')
            if not api_key:
                self.log('Can not extract api key from page source and meta')
                return self.parse(response)
            response.meta['api_key'] = api_key

            response.meta['next_link'] = self._get_next_results_page_link(response)

            url = self.SPONSORED_API.format(
                current_page=current_page,
                sku_list=sku_list,
                api_key=api_key
            )
            return Request(
                url,
                meta=response.meta,
                headers={
                    'Accept': '*/*',
                    'Accept-Encoding': ',gzip, deflate, br',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Connection': 'keep-alive',
                    'Host': 'www.hlserve.com',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36'
                },
                dont_filter=True,
                callback=self._parse_sponsored
            )

    def _parse_sponsored(self, response):
        meta = response.meta.copy()

        sponsored_prods = self._get_sponsored_prods(response)
        current_page = meta.get('current_page', 1)

        sponsored_links = meta.get('sponsored_links', [])

        if sponsored_prods:
            for (req, product) in response.meta['prod_requests'][current_page]:
                if self._parse_sku_from_url(req.url) in sponsored_prods:
                    sponsored_links.append(req.url)
                    cond_set_value(product, 'is_sponsored_product', True)
                else:
                    cond_set_value(product, 'is_sponsored_product', False)

            meta['sponsored_links'] = sponsored_links
            meta['current_page'] = current_page + 1

        next_link = meta.get('next_link')
        if next_link:
            return Request(
                next_link,
                meta=meta,
                callback=self._help_search
            )
        return self.parse(response)

    def _check_search_error(self, response):
        if not self._scrape_total_matches(response) and not response.meta.get('prod_requests'):
            self.log("Kohls: unable to find a match", ERROR)
            return True
        return False

    def not_a_product(self, response):
        if response.xpath('//div[@itemtype="http://schema.org/Product"]').extract():
            return False
        return True

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _is_not_found(self, response):
        if response.status == 404:
            return True

    def parse_product(self, response):
        prod = response.meta['product']
        prod['url'] = response.url

        if self._is_not_found(response):
            if 'pdp_outofstockproduct' in response.xpath('//div[@id="content"]/@class').extract():
                title = response.xpath('//div[@id="content"]//b/text()').extract()
                prod['title'] = title[0] if title else None
                prod['is_out_of_stock'] = True
                return prod
            else:
                prod['not_found'] = True
                return prod

        kv = KohlsVariants()
        kv.setupSC(response)
        prod['variants'] = kv._variants()

        reseller_id_regex = "prd-(\d+)"
        reseller_id = re.findall(reseller_id_regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(prod, 'reseller_id', reseller_id)

        cond_set_value(prod, 'locale', 'en-US')

        product_info_json = re.search("var\s?productV2JsonData\s?=\s?({.+);</script>", response.body_as_unicode())
        product_info_json = json.loads(product_info_json.group(1))

        selected_product = product_info_json.get("preSelectedColor")
        if selected_product:
            filtered_skus = [s for s in product_info_json.get(
                'SKUS', []) if s.get("color") == selected_product]
            if filtered_skus:
                upc = filtered_skus[0].get('UPC', {}).get('ID')
                prod['upc'] = upc[-12:].zfill(12) if upc else None

        prod['title'] = product_info_json.get("productTitle")

        prod['is_out_of_stock'] = not product_info_json.get("productStatus") == "In Stock"

        price = product_info_json.get("price", {}).get("salePrice", {})
        if not price:
            price = product_info_json.get("price", {}).get("regularPrice", {})
        price = price.get("minPrice") if price else None
        prod['price'] = Price(price=price, priceCurrency='USD')

        prod["image_url"] = product_info_json.get("variants", {}).get("largeImage")

        brand = product_info_json.get("monetization", {}).get("brand")
        if brand is not None:
            brand = brand.get("value")
        else:
            brand = guess_brand_from_first_words(prod.get('title', ""))
        prod["brand"] = brand

        prod['marketplace'] = []
        marketplace_name = is_empty(response.xpath(
            '//a[@id="pdp_vendor"]/text()').extract())
        if marketplace_name:
            marketplace = {
                'name': marketplace_name,
                'price': price
            }
        else:
            marketplace = {
                'name': 'Kohls',
                'price': price
            }
        prod['marketplace'].append(marketplace)

        return Request(self.url_formatter.format(
            self.REVIEW_URL, product_id=reseller_id),
            meta={'product': prod,
                  'product_id': reseller_id},
            callback=self._parse_reviews)

    def _parse_reviews(self, response):
        # TODO: refactor this method
        product = response.meta['product']
        text = response.body_as_unicode().encode('utf-8')
        if response.status == 200:
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
                        total = int(
                            total[0].replace(',', '')
                        )
                    except ValueError as exc:
                        total = 0
                        self.log(
                            "Error trying to extract number of BR in {url}: {exc}".format(
                                response.url, exc
                            ), WARNING
                        )
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
                        "/text()").re("(\d) star")
                    try:
                        if name:
                            name = int(name[0])
                        value = ih.xpath(
                            "span[@class='BVRRHistAbsLabel']/text()").extract()
                        if value:
                            value = int(
                                value[0].replace(',', '')
                            )
                        distribution[name] = value
                    except ValueError:
                        self.log(
                            "Error trying to extract {star} value of BR in {url}: {exc}".format(
                                star=name,
                                url=response.url,
                                exc=exc
                            ), WARNING
                        )
                if distribution:
                    reviews = BuyerReviews(total, avrg, distribution)
                    cond_set_value(product, 'buyer_reviews', reviews)
        if 'buyer_reviews' not in product:
            cond_set_value(product, 'buyer_reviews', ZERO_REVIEWS_VALUE)
        return product

    def _get_product_links(self, response):
        # V2
        prod_json_data = re.search('pmpSearchJsonData(.*?)</script>', response.body_as_unicode(),
                                   re.MULTILINE | re.DOTALL)
        if prod_json_data:
            prod_json_data = prod_json_data.group(1).strip()
            if prod_json_data.startswith('='):
                prod_json_data = prod_json_data[1:].strip()
            if prod_json_data.endswith(';'):
                prod_json_data = prod_json_data[0:-1].strip()

            products_list = re.findall('prodSeoURL[\"\']\s?:\s?[\"\']([^\.]+?\.jsp)', prod_json_data)

            collected_products = 0
            for prod_url in products_list:
                if prod_url:
                    if prod_url.startswith('/'):
                        prod_url = 'https://www.' + self.allowed_domains[0] + prod_url
                    collected_products += 1
                    product = SiteProductItem()
                    new_meta = {'product': product, 'handle_httpstatus_list': [404]}
                    yield Request(
                        prod_url,
                        callback=self.parse_product,
                        meta=new_meta,
                        errback=self._handle_product_page_error), product
            if collected_products:
                self.per_page = collected_products
                return

        prod_blocks = response.xpath('//ul[@id="product-matrix"]/li')

        if prod_blocks:
            for block in prod_blocks:
                product = SiteProductItem()
                link = block.xpath('./a/@href').extract()[0]

                cond_set(
                    product,
                    'title',
                    block.xpath('.//div/div/h2/a/text()').extract())

                cond_set(
                    product,
                    'image_url',
                    KohlsProductsSpider._fix_image_url(block.xpath('.//a/img/@src').extract())
                )

                self._set_price(response, product)

                url = 'https://www.kohls.com' + link
                cond_set_value(product, 'url', url)

                new_meta = {'product': product, 'handle_httpstatus_list': [404]}
                yield Request(
                    url,
                    callback=self.parse_product,
                    meta=new_meta,
                    errback=self._handle_product_page_error), product
        else:
            prod_urls = re.findall(
                r'"prodSeoURL"\s?:\s+\"(.+)\"',
                response.body_as_unicode()
            )
            for prod_url in prod_urls:
                self.per_page = len(prod_urls)

                product = SiteProductItem()
                new_meta = {'product': product, 'handle_httpstatus_list': [404]}
                url = 'https://www.' + self.allowed_domains[0] + prod_url

                yield Request(
                    url,
                    callback=self.parse_product,
                    meta=new_meta,
                    errback=self._handle_product_page_error), product

    def _handle_product_page_error(self, failure):
        self.log('Request failed: %s' % failure.request)
        product = failure.request.meta['product']
        product['locale'] = 'en-US'
        return failure.request.meta['product']

    def _scrape_total_matches(self, response):
        # V2
        count = re.search('productInfo\".*?count\":(.*?,)', response.body, re.MULTILINE)
        if count:
            count = count.group(1).replace(',', '').strip()
            if count and count.isdigit():
                return int(count)
        if response.xpath('//div[@class="search-failed"]').extract():
            print('Not Found')
            return 0
        else:
            total = response.xpath(
                '//span[@class="result_count"]/text()'
            ).re('\d{1,3}[,\d{3}]*')

            if total:
                total_matches = int(total[0].replace(',', ''))
            else:
                total_matches = is_empty(re.findall(
                    r'"allProducts":\s+\{(?:.|\n)\s+"count":( \d+)',
                    response.body_as_unicode()
                ), 0)
            try:
                total_matches = int(total_matches)
            except ValueError:
                    total_matches = 0
            return total_matches

    def _get_next_results_page_link(self, response):
        current_page = response.meta.get('current_page', 1)
        offset = current_page * 60
        if offset < response.meta.get('total_matches', 0):
            url = self.SEARCH_URL.format(search_term=response.meta['search_term'],
                                         start=offset,
                                         sort_mode=self.SORTING or '')
            return url

    def _scrape_next_results_page_link(self, response):
        if not response.meta.get('prod_requests'):
            current_page = response.meta.get('current_page', 1)
            next_link = self._get_next_results_page_link(response)
            response.meta['current_page'] = current_page + 1
            return Request(
                next_link,
                meta=response.meta
            )

    def _scrape_product_links(self, response):
        meta = response.meta.copy()
        prod_requests = meta.get('prod_requests')
        sponsored_links = meta.get('sponsored_links', [])
        if prod_requests:
            for page in prod_requests:
                for (req, product) in prod_requests[page]:
                    if sponsored_links:
                        cond_set_value(product, 'sponsored_links', sponsored_links)
                    yield req, product
        else:
            prods = list(self._get_product_links(response))
            for req in prods:
                yield req

    @staticmethod
    def _parse_sku_from_url(url):
        sku = re.search(r'-(\d+)/', url)
        return sku.group(1) if sku else None

    def _get_sponsored_prods(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            data = data.get('SearchProductAd', [])
            return [
                product.get('ParentSKU')
                for product in data
                if product.get('ParentSKU')
                ]
        except:
            self.log('Error parsing the sponsored products: {}'.format(traceback.format_exc()), WARNING)
            return []
