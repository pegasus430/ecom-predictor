# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals
from __future__ import print_function
from datetime import datetime
import re
import urlparse
import itertools, json

from scrapy.http import Request
from scrapy.log import WARNING
from product_ranking.amazon_tests import AmazonTests
from product_ranking.amazon_base_class import AmazonBaseClass
from product_ranking.validators.amazoncn_validator import AmazoncnValidatorSettings
from product_ranking.items import BuyerReviews
from product_ranking.utils import is_empty
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import FLOATING_POINT_RGEX


class AmazonProductsSpider(AmazonTests, AmazonBaseClass):
    name = 'amazoncn_products'
    allowed_domains = ["amazon.cn"]

    settings = AmazoncnValidatorSettings()

    use_proxies = True

    def __init__(self, *args, **kwargs):
        super(AmazonProductsSpider, self).__init__(*args, **kwargs)

        # String from html body that means there's no results ( "no results.", for example)
        self.total_match_not_found = '没有找到任何与'
        # Regexp for total matches to parse a number from html body
        self.total_matches_re = r'共\s?([\d,.\s?]+)'
        self.over_matches_re = r'共超过\s?([\d,.\s?]+)'

        self.avg_review_str = '颗星，最多 5 颗星'
        self.num_of_reviews_re = r'显示 .+? 条评论，共 ([\d,\.]+) 条评论'
        self.all_reviews_link_xpath = '//div[@id="revSum" or @id="reviewSummary"]' \
                                      '//a[contains(text(), "查看全部")]/@href'

        # Default price currency
        self.price_currency = 'CNY'
        self.price_currency_view = u'\uffe5'

        self.locale = 'zh_CN'

    # Captcha handling functions.
    def _has_captcha(self, response):
        is_captcha = response.xpath('.//*[contains(text(), "请输入您在这个图片中看到的字符")]')
        if is_captcha:
            self.log("Detected captcha, using captchabreaker", level=WARNING)
            return True
        return False

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

        except Exception as e:
            self.log('Error extracting v2 variants:', e)

        return variants

    def _parse_buyer_reviews(self, response):
        buyer_reviews = {}

        total = response.xpath(
            'string(//*[@id="summaryStars"])').re(FLOATING_POINT_RGEX)
        if not total:
            total = response.xpath(
                'string(//div[@id="acr"]/div[@class="txtsmall"]'
                '/div[contains(@class, "acrCount")])'
            ).re(FLOATING_POINT_RGEX)
        if not total:
            total = response.xpath('.//*[contains(@class, "totalReviewCount")]/text() | '
                                   '//span[@id="acrCustomerReviewText"]/text()').re(FLOATING_POINT_RGEX)
        if not total:
            return ZERO_REVIEWS_VALUE
        # For cases when total looks like: [u'4.2', u'5', u'51']
        if total:
            if len(total) == 3:
                buyer_reviews['num_of_reviews'] = int(total[-1].replace(',', '').
                                                      replace('.', ''))
            elif len(total) > 1:
                buyer_reviews['num_of_reviews'] = int(total[1].replace(',', '').
                                                      replace('.', ''))

        average = response.xpath(
            '//*[@id="summaryStars"]/a/@title')
        if not average:
            average = response.xpath(
                '//div[@id="acr"]/div[@class="txtsmall"]'
                '/div[contains(@class, "acrRating")]/text()'
            )
        if not average:
            average = response.xpath(
                ".//*[@id='reviewStarsLinkedCustomerReviews']//span/text()"
            )
        average = average.extract()[0].replace('out of 5 stars', '').replace(
            'von 5 Sternen', '').replace('5つ星のうち', '') \
            .replace('平均', '').replace(' 星', '').replace('étoiles sur 5', '') \
            .strip() if average else 0.0
        buyer_reviews['average_rating'] = float(average)

        buyer_reviews['rating_by_star'] = {}
        variants = self._parse_variants(response)
        buyer_reviews, table = self.get_rating_by_star(response, buyer_reviews, variants)

        if not buyer_reviews.get('rating_by_star'):
            # scrape new buyer reviews request (that will lead to a new page)
            buyer_rev_link = is_empty(response.xpath(
                '//div[@id="revSum" or @id="reviewSummary"]//a[contains(text(), "See all")'
                ' or contains(text(), "See the customer review")'
                ' or contains(text(), "See both customer reviews")'
                ' or contains(@id, "all-reviews")]/@href'
            ).extract())
            # Amazon started to display broken (404) link - fix
            if buyer_rev_link:
                buyer_rev_link = urlparse.urljoin(response.url, buyer_rev_link)
                buyer_rev_link = re.search(r'.*product-reviews/[a-zA-Z0-9]+/',
                                           buyer_rev_link)
                if buyer_rev_link:
                    buyer_rev_link = buyer_rev_link.group(0)
                    buyer_rev_req = Request(
                        url=buyer_rev_link,
                        callback=self.get_buyer_reviews_from_2nd_page
                    )
                    # now we can safely return Request
                    #  because it'll be re-crawled in the `parse_product` method
                    return buyer_rev_req

        return BuyerReviews(**buyer_reviews)

    def _format_last_br_date(self, date):
        """
        Parses date that is gotten from HTML.
        """
        date = re.findall(
            r'(\d+)',
            date
        )

        if date:
            date = ' '.join(date)
            d = datetime.strptime(date, '%Y %m %d')
            return d

        return None
