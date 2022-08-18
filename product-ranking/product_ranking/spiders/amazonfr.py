# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals
from __future__ import print_function

import re
import itertools, json
import traceback
from datetime import datetime

from urllib import unquote
from scrapy.conf import settings

from product_ranking.amazon_base_class import AmazonBaseClass
from product_ranking.utils import is_empty


class AmazonProductsSpider(AmazonBaseClass):
    name = 'amazonfr_products'
    allowed_domains = ["amazon.fr"]

    SEARCH_URL = "http://www.amazon.fr/s/?field-keywords={search_term}"

    REVIEW_DATE_URL = "http://www.amazon.fr/product-reviews/" \
                      "{product_id}/ref=cm_cr_pr_top_recent?" \
                      "ie=UTF8&showViewpoints=0&" \
                      "sortBy=bySubmissionDateDescending"

    def __init__(self, *args, **kwargs):
        super(AmazonProductsSpider, self).__init__(*args, **kwargs)

        # Variables for total matches method (_scrape_total_matches)
        self.total_match_not_found = 'ne correspond à aucun article.'
        self.total_matches_re = r'sur\s?([\d,.\s?]+)'
        self.over_matches_re = r'sur\s(.*?)\sr'

        self.avg_review_str = 'étoiles sur 5'
        self.num_of_reviews_re = r'(\d+)\scommentaires'
        self.all_reviews_link_xpath = '//div[@id="revSum" or @id="reviewSummary"]' \
                                      '//a[contains(text(), "Voir les")]/@href'

        # Price currency
        self.price_currency = 'EUR'
        self.price_currency_view = 'EUR'

        # Locale
        self.locale = 'fr_FR'

        settings.overrides['DEFAULT_REQUEST_HEADERS'] = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, sdch, br',
            'Accept-Language': 'en-US,en;q=0.8',
            'Connection': 'keep-alive',
            'Host': 'www.amazon.fr',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, '
                          'like Gecko) Chrome/52.0.2743.82 Safari/537.36'
        }

    def _format_last_br_date(self, date):
        """
        Parses date that is gotten from HTML.
        """
        months = {'janvier': 'January',
                  u'f\xe9vrier': 'February',
                  'mars': 'March',
                  'avril': 'April',
                  'mai': 'May',
                  'juin': 'June',
                  'juillet': 'July',
                  u'ao\xfbt': 'August',
                  'septembre': 'September',
                  'octobre': 'October',
                  'novembre': 'November',
                  u'd\xe9cembre': 'December'
                  }

        date = is_empty(
            re.findall(
                r'le (\d+ .+ \d+)',
                date
            )
        )

        if date:
            for key in months.keys():
                if key in date:
                    date = date.replace(key, months[key])

            d = datetime.strptime(date, '%d %B %Y')

            return d

        return None

    def _parse_variants(self, response):
        """
        Parses product variants.
        """
        variants = []
        try:
            canonical_link = response.xpath("//link[@rel='canonical']/@href").extract()
            original_product_canonical_link = canonical_link[0] if canonical_link else None
            variants_json_data = response.xpath('''.//script[contains(text(), "P.register('twister-js-init-dpx-data")]/text()''').extract()
            if variants_json_data:
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
        except:
            self.log('Error while extracting v2 variants: {}'.format(traceback.format_exc()))

        return variants
