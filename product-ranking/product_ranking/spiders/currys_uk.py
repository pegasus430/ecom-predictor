# -*- coding: utf-8 -*-

import re
import urlparse
import json
from itertools import ifilter
from decimal import Decimal, InvalidOperation

from scrapy import Request
from scrapy.log import ERROR

from product_ranking.items import SiteProductItem, valid_currency_codes, Price
from product_ranking.spiders import cond_set, cond_set_value, \
    _populate_from_open_graph_product, cond_replace_value, dump_url_to_file
from product_ranking.spiders.contrib.contrib import populate_reviews
from product_ranking.spiders.contrib.product_spider import ProductsSpider


SYM_USD = '$'
SYM_GBP = '£'
SYM_CRC = '₡'
SYM_EUR = '€'
SYM_JPY = '¥'

CURRENCY_SIGNS = {
    SYM_USD: 'USD',
    SYM_GBP: 'GBP',
    SYM_CRC: 'CRC',
    SYM_EUR: 'EUR',
    SYM_JPY: 'JPY'
}


def unify_decimal(ignored, float_dots):
    """ Create a function to convert various floating point textual
    representations to it's equivalent that can be converted to float directly.

    Usage:
       unify_float([ignored, float_dots])(string_:str) -> string

    Arguments:
       ignored - list of symbols to be removed from string
       float_dots - decimal/real parts separator

    Raises:
       `ValueError` - resulting string cannot be converted to float.
    """

    def unify_float_wr(string_):
        try:
            result = ''.join(['.' if c in float_dots else c for c in
                              string_ if c not in ignored])
            return str(Decimal(result))
        except InvalidOperation:
            raise ValueError('Cannot convert to decimal')

    return unify_float_wr


def unify_price(currency_codes, currency_signs, unify_decimal,
                default_currency=None):
    """Convert textual price representation to `Price` object.

    Usage:
       unify_price(currency_codes, currency_signs, unify_float,
       [default_currency])(string_) -> Price

    Arguments:
       currency_codes - list of possible currency codes (like ['EUR', 'USD'])
       currency_signs - dictionary to convert substrings to currency codes
       unify_decimal - function to convert price part into decimal
       default_currency - default currency code

    Raises:
       `ValueError` - no currency code found and default_curreny is None.
    """

    def unify_price_wr(string_):
        string_ = string_.strip()
        sorted_ = sorted(currency_signs.keys(), None, len, True)
        sign = next(ifilter(string_.startswith, sorted_), '')
        string_ = currency_signs.get(sign, '') + string_[len(sign):]
        sorted_ = sorted(currency_codes, None, len, True)
        currency = next(ifilter(string_.startswith, sorted_), None)

        if currency is None:
            currency = default_currency
        else:
            string_ = string_[len(currency):]

        if currency is None:
            raise ValueError('Could not get currency code')

        float_string = unify_decimal(string_.strip())

        return Price(currency, float_string)

    return unify_price_wr


class CurrysUkProductsSpider(ProductsSpider):
    """ currys.co.uk product ranking spider

    Spider takes `order` argument with possible sorting modes:

    * `relevance` (default)
    * `brand_asc`, `brand_desc`
    * `price_asc`, `price_desc`
    * `rating`

    Following fields are not scraped:

    * `model`, `upc`, `related_products`, `buyer_reviews`
    """

    name = 'currys_uk_products'

    allowed_domains = [
        'currys.co.uk'
    ]

    SEARCH_URL = "http://www.currys.co.uk/gbuk/search-keywords" \
                 "/xx_xx_xx_xx_xx/{search_term}/1_20" \
                 "/{sort_mode}/xx-criteria.html"

    SORT_MODES = {
        'default': 'relevance-desc',
        'relevance': 'relevance-desc',
        'brand_asc': 'brand-asc',
        'brand_desc': 'brand-desc',
        'price_asc': 'price-asc',
        'price_desc': 'price-desc',
        'rating': 'rating-desc'
    }

    REVIEWS_URL = "http://mark.reevoo.com/reevoomark/en-GB/" \
                  "product?sku=%s&trkref=CYS"

    HARDCODED_FIELDS = {
        'locale': 'en-GB'
    }

    OPTIONAL_REQUESTS = {
        'buyer_reviews': True
    }

    def start_requests(self):
        for req in super(CurrysUkProductsSpider, self).start_requests():
            req.meta.update({'dont_redirect': True,
                             'handle_httpstatus_list': [302, 301]})
            yield req

    def parse(self, response):
        if response.status == 302 or response.status == 301:
            location = response.headers['Location']

            # force sort mode
            url_parts = urlparse.urlsplit(location)
            if re.search(r'xx-criteria\.html$', url_parts.path):
                path_with_sort = re.sub(r'/(1_20/[^/]+/)?(xx-criteria\.html)$',
                                        '/1_20/{}/\g<2>'.format(self.sort_mode),
                                        url_parts.path)
                location = url_parts._replace(path=path_with_sort).geturl()

            request = Request(urlparse.urljoin(response.url, location),
                              meta=response.meta, dont_filter=True)
            yield request
        else:
            for item in super(CurrysUkProductsSpider, self).parse(response):
                yield item

    def _total_matches_from_html(self, response):
        if self._is_product_page(response):
            return 1

        matches = response.xpath(".//span[text()='Showing']/following-sibling::text()").extract()

        if matches:
            matches = re.search(r'\d+\s*-\s*\d+\s*of\s*(\d+)', matches[0])

            if matches:
                return int(matches.group(1))

        return None

    def _scrape_next_results_page_link(self, response):
        next_url = response.xpath(".//*[@class='pagination']//a[@class='next']/@href").extract()

        if next_url:
            return next_url[0]

        return None

    def _is_product_page(self, response):
        return response.xpath(".//meta[@property='og:type' and @content='product']")

    def _scrape_product_links(self, response):
        if self._is_product_page(response):
            product = SiteProductItem()
            response.meta['product'] = product

            request = Request(response.url,
                              callback=self.parse_product,
                              meta=response.meta,
                              errback=self._handle_product_page_error,
                              dont_filter=True)

            yield request, product
        else:
            items = super(CurrysUkProductsSpider, self)._scrape_product_links(response)

            for item in items:
                yield item

    def _fetch_product_boxes(self, response):
        return response.xpath(".//article[contains(@class,'product')]")

    def _link_from_box(self, box):
        link = box.xpath(".//a[@class='in']/@href").extract()

        if link:
            return link[0]

        return None

    def _populate_from_box(self, response, box, product):
        cond_set(product, 'title', box.xpath(".//*[@class='productTitle']/*[@data-product='name']/text()").extract())
        cond_set(product, 'brand', box.xpath(".//*[@class='productTitle']/*[@data-product='brand']/text()").extract())
        cond_set(product, 'price', box.xpath(".//*[@class='price']/text()").extract(), unicode.strip)

        cond_set_value(product, 'is_in_store_only',
                       bool(box.xpath(".//*[@data-availability='homeDeliveryUnavailable']")))

        cond_set_value(product, 'is_out_of_stock', bool(box.xpath(".//*[@class='nostock']")))

    def _populate_from_html(self, response, product):
        self._populate_from_json(response, product)

        cond_set(product, 'image_url', response.xpath(".//*[@class='product-image']/@src").extract())

        _populate_from_open_graph_product(response, product)

        cond_set(product, 'price',
                 response.xpath(".//*[@id='product-main']//*[@data-key='current-price']/text()").extract(),
                 unicode.strip)

        cond_set(product, 'brand',
                 response.xpath(".//*[contains(@class,'page-title')]/span[1]/text()").extract())

        cond_set(product, 'title',
                 response.xpath(".//*[contains(@class,'page-title')]/span[2]/text()").extract())

        cond_set(product, 'description', response.xpath(".//*[@id='product-info']/article").extract())

        cond_set(product, 'sku', response.xpath(".//*[@class='prd-code']/text()").re('\d+'))
        cond_set_value(product, 'reseller_id', product.get('sku'))

        cond_set_value(product, 'is_out_of_stock', bool(response.xpath(".//*[@class='nostock']")))

        cond_set_value(product, 'is_in_store_only',
                       bool(response.xpath(".//*[@class='unavailable']/i[@class='dcg-icon-delivery']")))

        categories = response.xpath(".//*[@class='breadcrumb']/a/span/text()").extract()
        if categories:
            cond_set_value(product, 'categories', categories)
            cond_set_value(product, 'category', categories[-1])

        if not isinstance(product.get('price'), Price):
            self._unify_price(product)

        if not product.get('brand'):
            dump_url_to_file(response.url)

    def _populate_from_json(self, response, product):
        json_data = response.xpath(".//*[@id='content']/script[@type='application/ld+json']/text()").extract()
        if json_data:
            try:
                breadcrumbs_data = json.loads(json_data[0])

                categories = [x.get('item', {}).get('name') for x in breadcrumbs_data.get('itemListElement', [])]
                if categories:
                    cond_set_value(product, 'categories', categories)
                    cond_set_value(product, 'category', categories[-1])
            except Exception as e:
                self.log(str(e), ERROR)

            try:
                product_data = json.loads(json_data[1])

                cond_set_value(product, 'title', product_data.get('name'))
                cond_set_value(product, 'sku', product_data.get('sku'))
                cond_set_value(product, 'reseller_id', product.get('sku'))
                cond_set_value(product, 'image_url', product_data.get('image'))

                if product_data.get('offers'):
                    offer = product_data.get('offers')
                    offer_type = offer.get('@type')
                    offer_currency = offer.get('priceCurrency')

                    if offer_type == 'Offer':
                        cond_set_value(product, 'price', Price(offer_currency, offer.get('price')))
                    if offer_type == 'AggregateOffer':
                        cond_set_value(product, 'price', Price(offer_currency, offer.get('lowPrice')))

                    cond_set_value(product, 'is_out_of_stock',
                                   offer.get('availability') == 'http://schema.org/OutOfStock')

                cond_set_value(product, 'brand', product_data.get('brand', {}).get('name'))
                cond_set_value(product, 'description', product_data.get('description'))
            except Exception as e:
                self.log(str(e), ERROR)

    def _unify_price(self, product):
        price = product['price'].encode('utf-8')
        price = unify_price(valid_currency_codes, CURRENCY_SIGNS,
                            unify_decimal(', ', '.'))(price)

        cond_replace_value(product, 'price', price)

    def _request_buyer_reviews(self, response):
        product_id = response.xpath(".//*[@name='sFUPID']/@value").extract()
        if product_id:
            return 'http://mark.reevoo.com/reevoomark/en-GB/product?sku={}&trkref=CYS'.format(product_id[0])

    def _parse_buyer_reviews(self, response):
        field_name = response.meta['field']
        scores = response.meta.get('scores', list())

        is_reviews = response.xpath('//a[@id="reviews-tab-content-link"]')
        if not is_reviews:
            return None

        page_scores = response.xpath(".//*[@class='overall-scores']/div/@title").extract()
        page_scores = map(float, filter(unicode.isdigit, page_scores))
        scores.extend(page_scores)

        next_page = response.xpath(".//a[@class='next_page']/@href").extract()
        if next_page:
            next_page = urlparse.urljoin(response.url, next_page[0])

            new_meta = response.meta.copy()
            new_meta['scores'] = scores

            return Request(next_page,
                           callback=getattr(self, '_parse_' + field_name),
                           meta=new_meta,
                           errback=self._handle_option_error,
                           dont_filter=True)
        else:
            populate_reviews(response, scores)

    def _parse_single_product(self, response):
        return self.parse_product(response)
