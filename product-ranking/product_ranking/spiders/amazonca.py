# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import re

from datetime import datetime
from scrapy import Request
from scrapy.log import WARNING, ERROR

from product_ranking.amazon_base_class import AmazonBaseClass
from product_ranking.amazon_tests import AmazonTests
from product_ranking.utils import is_empty
from product_ranking.validators.amazonca_validator import \
    AmazoncaValidatorSettings


class AmazonProductsSpider(AmazonTests, AmazonBaseClass):
    name = 'amazonca_products'
    allowed_domains = ["www.amazon.ca", "amazon.com"]

    settings = AmazoncaValidatorSettings

    QUESTIONS_URL = "https://www.amazon.ca/ask/questions/inline/{asin_id}/{page}"

    def __init__(self, *args, **kwargs):
        super(AmazonProductsSpider, self).__init__(*args, **kwargs)


        # String from html body that means there's no results ( "no results.", for example)
        self.total_match_not_found_re = 'did not match any products.'
        # Regexp for total matches to parse a number from html body
        self.total_matches_re = r'of\s?([\d,.\s?]+)'
        self.other_total_matches_re = r'([\d,\s]+)results\sfor'
        self.over_matches_re = r'over\s?([\d,.\s?]+)'

        # Default price currency
        self.price_currency = 'CAD'
        self.price_currency_view = '$'

        # Locale
        self.locale = 'en_CA'

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

    def _scrape_total_matches(self, response):
        total_match_not_found_re = getattr(self, 'total_match_not_found_re', '')
        total_matches_re = getattr(self, 'total_matches_re', '')
        other_total_matches_re = getattr(self, 'other_total_matches_re', '')
        over_matches_re = getattr(self, 'over_matches_re', '')

        if not total_match_not_found_re and not total_matches_re and not other_total_matches_re and not over_matches_re:
            self.log('Either total_match_not_found_re or total_matches_re '
                     'is not defined. Or both.', ERROR)
            return None

        if unicode(total_match_not_found_re) in response.body_as_unicode():
            return 0

        count_matches = self._is_empty(
            response.xpath(
                '//*[@id="s-result-count"]/text()'
            ).re(unicode(total_matches_re))
        )
        if not count_matches:
            count_matches = self._is_empty(
                response.xpath(
                    '//*[@id="s-result-count"]/text()'
                ).re(unicode(other_total_matches_re))
            )

        total_matches = self._get_int_from_string(count_matches.replace(',', '')) if count_matches else 0
        if total_matches == 0:
            over_matches = self._is_empty(
                response.xpath(
                    '//*[@id="s-result-count"]/text()'
                ).re(unicode(over_matches_re))
            )
            total_matches = self._get_int_from_string(over_matches.replace(',', '')) if over_matches else 0

        return total_matches

    @staticmethod
    def _parse_upc(response):
        upc = (AmazonBaseClass._parse_upc(response)
               or response.xpath('//th[contains(text(), "UPC")]/following-sibling::td/text()').re('[\d\w]+'))
        return is_empty(upc) if isinstance(upc, list) else upc

    def _parse_questions(self, response):
        asin_id = response.xpath(
            '//input[@id="ASIN"]/@value').extract() or \
            re.findall('"ASIN":"(.*?)"', response.body)
        if asin_id:
            return Request(self.QUESTIONS_URL
                               .format(asin_id=asin_id[0], page="1"),
                           callback=self._parse_recent_questions, dont_filter=True)

        return None

    def _parse_recent_questions(self, response):
        product = response.meta['product']
        reqs = response.meta.get('reqs', [])

        recent_questions = product.get('recent_questions', [])
        questions = response.css('.askTeaserQuestions > div')
        for question in questions:
            q = {}

            question_summary = self._is_empty(
                question.xpath('.//div[span[text()="Question:"]]'
                               '/following-sibling::div[1]/a/text()')
                .extract())
            question_summary = (question_summary.strip()
                                if question_summary
                                else question_summary)
            q['questionSummary'] = question_summary

            question_id = self._is_empty(
                question.xpath('.//div[span[text()="Question:"]]/'
                               'following-sibling::div[1]/a/@href')
                .re('/forum/-/(.*)?/'))
            if not question_id:
                question_id = question.xpath('.//div[contains(@id, "question-")]/@id').extract()

            if isinstance(question_id, list):
                q['questionId'] = question_id[0]
            else:
                q['questionId'] = question_id
            q['voteCount'] = self._is_empty(
                question.xpath('.//@data-count').extract())

            q['answers'] = []
            answers = question.xpath(
                './/div[span[text()="Answer:"]]/following-sibling::div')
            for answer in answers:
                a = {}
                name = self._is_empty(
                    question.xpath('.//*[@class="a-color-tertiary"]/text()')
                    .re('By (.*) on '))
                name = name.strip() if name else name
                a['userNickname'] = name

                date = self._is_empty(
                    question.xpath('.//*[@class="a-color-tertiary"]/text()')
                    .re(' on (\w+ \d+, \d+)'))
                a['submissionDate'] = date
                q['submissionDate'] = date

                answer_summary = ''.join(
                    answer.xpath('span[1]/text()|'
                                 'span/span[@class="askLongText"]/text()')
                    .extract())

                a['answerSummary'] = (answer_summary.strip()
                                      if answer_summary
                                      else answer_summary)

                q['answers'].append(a)

            q['totalAnswersCount'] = len(q['answers'])

            recent_questions.append(q)

        if recent_questions:
            product['recent_questions'] = recent_questions

        if questions:
            try:
                current_page = int(re.search('/(\d+)$', response.url).group(1))
                url = re.sub('/\d+$', "/%d" % (current_page + 1), response.url)
                reqs.append(
                    Request(url, callback=self._parse_recent_questions, dont_filter=True))
            except Exception as e:
                self.log('Error while parse question page. ERROR: %s.' %
                         str(e), WARNING)
                pass

        if reqs:
            return self.send_next_request(reqs, response)

        return product
