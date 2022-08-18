# -*- coding: utf-8 -*-

import json
import urlparse
from itertools import ifilter
from decimal import Decimal, InvalidOperation

from product_ranking.items import RelatedProduct, valid_currency_codes
from product_ranking.spiders import cond_set, cond_replace, cond_set_value, \
    dump_url_to_file
from product_ranking.spiders.contrib.product_spider import ProductsSpider
from product_ranking.items import Price, MarketplaceSeller
import re
from product_ranking.items import Price


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


class EbayUkProductsSpider(ProductsSpider):
    """ ebay.co.uk product ranking spider

    Spider takes `order` argument with possible sort modes:

    * `relevance`
    * `old`, `new`
    * `price_pp_asc`, `price_pp_desc`
    * `price_asc`, `price_desc`
    * `condition_new`, `condition_used`
    * `distance_asc`


    There are following caveats:

    * `is_out_of_stock`, `is_in_store_only`, `upc`, `buyer_reviews` are not scraped
    """

    name = 'ebay_uk_products'

    allowed_domains = ['ebay.co.uk']

    SEARCH_URL = "http://www.ebay.co.uk/sch/i.html" \
                 "?_sacat=0&_nkw={search_term}&_sop={sort_mode}" \
                 "&_fcid={country_id}&_dmd=1"

    SORT_MODES = {
        'default': 12,
        'relevance': 12,
        'old': 1,  #Time - ending soonest
        'new': 10,
        'price_pp_asc': 15,
        'price_pp_desc': 16,
        'price_asc': 2,
        'price_desc': 3,
        'condition_new': 18,
        'condition_used': 19,
        'distance_asc': 7
    }

    OPTIONAL_REQUESTS = {
        'related_products': True
    }

    HARDCODED_FIELDS = {
        'locale': 'en-GB'
    }

    def __init__(self, country=3, *args, **kwargs):
        super(EbayUkProductsSpider, self).__init__(*args, **kwargs)
        self.url_formatter.defaults['country_id'] = country

    def _total_matches_from_html(self, response):
        matches = response.css('.rcnt::text')
        if not matches:
            return 0
        try:
            return int(matches.extract()[0].replace(',', ''))
        except ValueError:
            return 0

    def _scrape_next_results_page_link(self, response):
        link = response.css('.pagn-next a::attr(href)')
        if link:
            return link.extract()[0]

    def _fetch_product_boxes(self, response):
        return response.css('#ResultSetItems #ListViewInner .sresult.lvresult')

    def _link_from_box(self, box):
        return box.css('.lvtitle a::attr(href)').extract()[0]

    def _populate_from_box(self, response, box, product):
        cond_set(product, 'title', box.css('.lvtitle a::text').extract())
        cond_set(product, 'price', box.css('.g-b::text').extract(),
                 self._unify_price)
        cond_set(product, 'image_url', box.css('img.img::attr(src)').extract())

    def _populate_from_html(self, response, product):
        self._populate_hardcoded_fields(product)
        cond_set(product, 'title', response.css('#itemTitle::text').extract())
        cond_set(product, 'price',
                 response.css('[itemprop=price]::text , '
                              '#mm-saleDscPrc::text').extract(),
                 self._unify_price)

        seller = response.xpath(
            '//div[@class="mbg"]/a/span/text()'
        ).extract()

        if seller:
            seller = seller[0].strip()
            product["marketplace"] = [{
                "name": seller,
                "price": product.get("price", None)
            }]

        cond_replace(product, 'image_url',
                     response.css('[itemprop=image]::attr(src)').extract())
        xpath = '//*[@id="vi-desc-maincntr"]/node()[normalize-space()]'
        cond_set_value(product, 'description',
                       response.xpath(xpath).extract(), ''.join)
        cond_replace(product, 'url',
                     response.css('[rel=canonical]::attr(href)').extract())
        xpath = '//td[@class="attrLabels" and contains(text(), "Brand:")]' \
                '/following-sibling::td/span/text()'
        cond_set(product, 'brand', response.xpath(xpath).extract())
        if not product.get('brand', None):
            dump_url_to_file(response.url)
        xpath = '//td[@class="attrLabels" and contains(text(), "Model:")]' \
                '/following-sibling::td/span/text()'
        cond_set(product, 'model', response.xpath(xpath).extract())

        reseller_id_regex = "-\/([^\/&?\.\s]+)"
        reseller_id = re.findall(reseller_id_regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, 'reseller_id', reseller_id)


    def _request_related_products(self, response):
        id_ = response.css('*::attr(data-itemid)').extract()
        if not id_:
            return
        id_ = id_[0]
        if not id_.isdigit():
            return
        return "http://www.ebay.com/rec/plmt/100009-100010-100047?itm=%s" % id_

    def _parse_related_products(self, response):
        try:
            json_ = json.loads(response.body_as_unicode())
        except ValueError:
            return None
        related_products = {}
        for relation in json_.itervalues():
            name = relation.get('templateHeader')
            if not name:
                continue
            products = []
            for reco in relation.get('recos'):
                title = reco.get('title')
                url = reco.get('url')
                if not (title and url):
                    continue
                d = urlparse.urlsplit(url, False)
                url = urlparse.urlunsplit([d[0], d[1], d[2], '', ''])
                products.append(RelatedProduct(url, title))
            if products:
                related_products[name] = products
        cond_set_value(response.meta['product'], 'related_products',
                       related_products or None)

    def _unify_price(self, price):
        price = price.strip().encode('utf-8')
        try:
            price = unify_price(valid_currency_codes, CURRENCY_SIGNS,
                                unify_decimal(', ', '.'),
                            'GBP')(price)
        except ValueError:
            return None
        else:
            return price

    def _parse_single_product(self, response):
        return self.parse_product(response)
