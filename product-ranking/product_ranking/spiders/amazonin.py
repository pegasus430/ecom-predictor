# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals
from __future__ import print_function
from datetime import datetime
import re
import urlparse
import json
import itertools

from scrapy import Request

from product_ranking.items import Price
from product_ranking.spiders import FLOATING_POINT_RGEX
from product_ranking.amazon_tests import AmazonTests
from product_ranking.amazon_base_class import AmazonBaseClass
from product_ranking.validators.amazon_validator import AmazonValidatorSettings


class AmazonProductsSpider(AmazonTests, AmazonBaseClass):
    name = 'amazonin_products'
    allowed_domains = ["www.amazon.in"]

    SEARCH_URL = "http://www.amazon.in/s/ref=nb_sb_noss_2?url=search-alias%3Dstripbooks&field-keywords={search_term}"

    user_agent = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:35.0) Gecko'
                  '/20100101 Firefox/35.0')

    settings = AmazonValidatorSettings

    def __init__(self, *args, **kwargs):
        super(AmazonProductsSpider, self).__init__(*args, **kwargs)

        # String from html body that means there's no results ( "no results.", for example)
        self.total_match_not_found_re = 'did not match any products.'
        # Regexp for total matches to parse a number from html body
        self.total_matches_re = r'of\s?([\d,.\s?]+)'
        self.over_matches_re = r'over\s?([\d,.\s?]+)'

        # Default price currency
        self.price_currency = u'INR'
        # There is no currency symbol on the page, only space symbol before price value
        self.price_currency_view = u' '

        # Locale
        self.locale = 'en-US'

    def _format_last_br_date(self, date):
        """
        Parses date that is gotten from HTML.
        """
        date = self._is_empty(
            re.findall(
                r'on (\w+ \d+, \d+)', date
            ), ''
        )

        if date:
            date = date.replace(',', '').replace('.', '')

            try:
                d = datetime.strptime(date, '%B %d %Y')
            except ValueError:
                d = datetime.strptime(date, '%b %d %Y')

            return d

        return None

    def _parse_marketplace_from_static_right_block_more(self, response):
        product = response.meta['product']
        reqs = response.meta.get('reqs')

        _prod_price = product.get('price', [])
        _prod_price_currency = None
        if _prod_price:
            _prod_price_currency = _prod_price.priceCurrency

        _marketplace = product.get('marketplace', [])
        for seller_row in response.xpath('//*[@id="olpOfferList"]//div[contains(@class,"olpOffer")]'):
            _name = seller_row.xpath(
                '*//h3[contains(@class,"olpSellerName")]//a/text()|'
                '*//h3[contains(@class,"olpSellerName")]//img/@alt').extract()
            _price = seller_row.xpath(
                '*//*[contains(@class,"olpOfferPrice")]/span/text()').extract()
            _price = float(self._strip_currency_from_price(
                self._fix_dots_commas(_price[0].strip()))) if _price else None

            _seller_id = seller_row.xpath('*//h3//a/@href').re('seller=(.*)\&?') or seller_row.xpath(
                '*//h3//a/@href').re('shops/(.*?)/')
            _seller_id = _seller_id[0] if _seller_id else None

            if _name:
                _name = self._marketplace_seller_name_parse(_name[0])
                _marketplace.append({
                    'name': _name.replace('\n', '').strip(),
                    'price': _price,
                    'currency': _prod_price_currency,
                    'seller_id': _seller_id
                })

        next_page = response.xpath('//*[@class="a-pagination"]/li[@class="a-last"]/a/@href').extract()
        meta = response.meta
        if next_page:
            return Request(
                url=urlparse.urljoin(response.url, next_page[0]),
                callback=self._parse_marketplace_from_static_right_block_more,
                meta=response.meta,
                dont_filter=True
            )

        elif reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_variants(self, response):
        """
        Parses product variants.
        """
        variants = []
        try:
            canonical_link = response.xpath("//link[@rel='canonical']/@href").extract()
            original_product_canonical_link = canonical_link[0] if canonical_link else None
            variants_json_data = response.xpath('''.//script[contains(text(), "P.register('twister-js-init-dpx-data")]/text()''').extract()

            if not variants_json_data:
                return None

            variants_json_data = re.findall('var\s?dataToReturn\s?=\s?({.+});', variants_json_data[0], re.DOTALL)
            cleared_vardata = variants_json_data[0].replace("\n", "")
            cleared_vardata = re.sub("\s\s+", "", cleared_vardata)
            cleared_vardata = cleared_vardata.replace(',]', ']').replace(',}', '}')
            variants_data = json.loads(cleared_vardata)
            all_variations_array = variants_data.get("dimensionValuesData", [])
            all_combos = list(itertools.product(*all_variations_array))
            all_combos = [list(a) for a in all_combos]
            asin_combo_dict = variants_data.get("dimensionValuesDisplayData", {})
            props_names = variants_data.get("dimensionsDisplay", [])
            instock_combos = []
            all_asins = []
            # Fill instock variants
            for asin, combo in asin_combo_dict.items():
                all_asins.append(asin)
                instock_combos.append(combo)
                variant = {}
                variant["asin"] = asin
                properties = {}
                for index, prop_name in enumerate(props_names):
                    properties[prop_name] = combo[index]
                variant["properties"] = properties
                variant["in_stock"] = True
                variants.append(variant)
                if original_product_canonical_link:
                    variant["url"] = "/".join(original_product_canonical_link.split("/")[:-1]) + "/{}".format(asin)
                else:
                    variant["url"] = "/".join(self.product_url.split("/")[:-1]) + "/{}".format(asin)

            oos_combos = [c for c in all_combos if c not in instock_combos]
            for combo in oos_combos:
                variant = {}
                properties = {}
                for index, prop_name in enumerate(props_names):
                    properties[prop_name] = combo[index]
                variant["properties"] = properties
                variant["in_stock"] = False
                variants.append(variant)
            # Price for variants is extracted on SC - scraper side, maybe rework it here as well?
        except Exception as e:
            print ('Error extracting v2 variants:', e)
        return variants
