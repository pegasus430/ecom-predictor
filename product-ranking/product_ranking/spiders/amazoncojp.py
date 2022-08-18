# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals
from __future__ import print_function
import re
from datetime import datetime

from product_ranking.amazon_tests import AmazonTests
from product_ranking.amazon_base_class import AmazonBaseClass
from product_ranking.validators.amazoncojp_validator import AmazoncojpValidatorSettings


class AmazonProductsSpider(AmazonTests, AmazonBaseClass):
    name = 'amazonjp_products'
    allowed_domains = ["amazon.co.jp"]

    settings = AmazoncojpValidatorSettings()

    def __init__(self, *args, **kwargs):
        super(AmazonProductsSpider, self).__init__(*args, **kwargs)

        # Variables for total matches method (_scrape_total_matches)
        self.total_match_not_found = '検索に一致する商品はありませんでした'
        self.total_matches_re = r'検索結果\s?([\d,.\s?]+)'
        self.over_matches_re = r'検索結果 ([\d,.\s?]+) 以上 のうち'

        self.avg_review_str = '5つ星のうち'
        self.num_of_reviews_re = r'([\d,\.]+)件中.+?件目のレビューを表示'
        self.all_reviews_link_xpath = '//div[@id="revSum" or @id="reviewSummary"]' \
                                      '//a[contains(text(), "すべてのカスタマーレビュー")]/@href'

        # Price currency
        self.price_currency = 'JPY'
        self.price_currency_view = '￥'

        self.locale = 'ja_JP'

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
