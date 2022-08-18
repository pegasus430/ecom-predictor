# -*- coding: utf-8 -*-#
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import re
import json

from datetime import datetime
from urlparse import urljoin

from scrapy import Request
from scrapy.log import WARNING
from scrapy.conf import settings

from product_ranking.amazon_base_class import AmazonBaseClass
from product_ranking.amazon_tests import AmazonTests
from product_ranking.guess_brand import guess_brand_from_first_words, find_brand
from product_ranking.validators.amazon_validator import AmazonValidatorSettings


class AmazonProductsSpider(AmazonTests, AmazonBaseClass):
    name = 'amazon_products'
    allowed_domains = ["www.amazon.com"]

    QUESTIONS_URL = "https://www.amazon.com/ask/questions/inline/{asin_id}/{page}"

    def __init__(self, *args, **kwargs):
        super(AmazonProductsSpider, self).__init__(*args, **kwargs)

        self.captcha_retries = 20

        detect_ads = kwargs.pop('detect_ads', False)
        self.detect_ads = detect_ads in (1, '1', 'true', 'True', True)

        self.settings = AmazonValidatorSettings(spider_class=self)

        # String from html body that means there's no results ( "no results.", for example)
        self.total_match_not_found_re = 'did not match any products.'
        # Regexp for total matches to parse a number from html body
        self.total_matches_re = r'of\s?([\d,.\s?]+)'
        self.other_total_matches_re = r'([\d,\s]+)results\sfor'
        self.over_matches_re = r'over\s?([\d,.\s?]+)'

        # Default price currency
        self.price_currency = 'USD'
        self.price_currency_view = '$'

        self.scrape_questions = kwargs.get('scrape_questions', None)
        if self.scrape_questions not in ('1', 1, True, 'true', 'True') or self.summary:
            self.scrape_questions = False

        # Locale
        self.locale = 'en-US'

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        settings.overrides['DUPEFILTER_CLASS'] = 'product_ranking.utils.BaseDupeFilter'

    def start_requests(self):

        for request in super(AmazonProductsSpider, self).start_requests():
            if not self.product_url and self.detect_ads:
                request = request.replace(callback=self._get_ads_links)
            yield request.replace(dont_filter=True)

    def _get_ads_links(self, response):
        ads_xpath = '//a[@class="clickthroughLink textLink"]'
        ads_images_xpath = '//a[@class="clickthroughLink asinImage"]//div[@class="imageContainer"]'
        ads_links = response.xpath(ads_xpath + '/@href').extract()
        ads_images = response.xpath(ads_images_xpath + '/img/@src').extract()
        if not ads_images:
            ads_images = response.xpath('//a[contains(@class, "clickthroughLink")]'
                                        '//img[contains(@class, "mediaCentralImage")]/@src').extract()
        prod_links = list(self._scrape_product_links(response))
        sponsored_links = list(self._get_sponsored_links(response))
        total_matches = self._scrape_total_matches(response)
        next_page_link = self._scrape_next_results_page_link(response)
        ads = []
        if ads_links and ads_images:
            ads = [{
                'ad_url': urljoin(response.url, ad_url),
                'ad_image': ads_images[i],
                'ad_dest_products': []
            } for i, ad_url in enumerate(ads_links)]

        meta = response.meta.copy()
        if ads and prod_links:
            meta['ads'] = ads
            meta['prod_links'] = prod_links
            meta['sponsored_links'] = sponsored_links
            meta['total_matches'] = total_matches
            meta['next_page_link'] = next_page_link
            meta['idx'] = 0
            return Request(
                url=ads[0]['ad_url'],
                callback=self._parse_ads_links,
                dont_filter=True,
                meta=meta
            )
        return self.parse(response)

    def _parse_ads_links(self, response):
        meta = response.meta.copy()
        idx = meta.get('idx', 0)
        ads = meta.get('ads')

        if ads:
            return Request(
                url=ads[idx]['ad_url'],
                callback=self._parse_ads_products,
                dont_filter=True,
                meta=meta
            )
        return self.parse(response)

    def _parse_ads_products(self, response):
        idx = response.meta.get('idx')
        ads = response.meta.get('ads')

        ads_products = re.search(r'var config = (\{.*?\});', response.body, re.DOTALL)
        if ads_products and ads_products.group(1):
            try:
                ads_products = json.loads(ads_products.group(1)).get('content', {}).get('products')
                if ads_products:
                    for ads_product in ads_products:
                        link = ads_product.get('links').get('links')[0].get('url')
                        title = ads_product.get('title').get('displayString')
                        if link and title:
                            ads[idx]['ad_dest_products'].append({
                                'name': title,
                                'url': urljoin(response.url, link),
                                'brand': guess_brand_from_first_words(title),
                                'reseller_id': self._get_reseller_id(link)
                            })
            except:
                self.log('content: {}'.format(response))

        if len(ads[idx]['ad_dest_products']) == 0:
            base_xpathes = response.xpath(
                '//div[@class="s-item-container"]//a[contains(@class, "s-access-detail-page")]')
            if base_xpathes:
                for base in base_xpathes:
                    link = base.xpath('./@href').extract()
                    title = base.xpath('./@title').extract()
                    if link and title:
                        ads[idx]['ad_dest_products'].append({
                            'name': title[0],
                            'url': urljoin(response.url, link[0]),
                            'brand': guess_brand_from_first_words(title[0]),
                            'reseller_id': self._get_reseller_id(link[0])
                        })
            else:
                base_xpathes = response.xpath('//div[contains(@class, "stores-column")]//ul//li')
                if base_xpathes:
                    for base in base_xpathes:
                        link = base.xpath('.//a//@href').extract()
                        title = base.xpath('//a/div/img/@alt').extract()
                        if link and title:
                            ads[idx]['ad_dest_products'].append({
                                'name': title[0],
                                'url': urljoin(response.url, link[0]),
                                'brand': guess_brand_from_first_words(title[0]),
                                'reseller_id': self._get_reseller_id(link[0])
                            })

        response.meta['ads'] = ads
        if response.meta.get('asins', []):
            return self._parse_ads_links(response)

        if idx + 1 < len(ads):
            idx += 1
            response.meta['idx'] = idx
            return Request(
                url=ads[idx]['ad_url'],
                meta=response.meta,
                dont_filter=True,
                callback=self._parse_ads_links
            )
        return self.parse(response)

    def _get_sponsored_links(self, response):
        sponsored_links = []
        links = response.xpath("//a[contains(@class, 's-access-detail-page')]/@href").extract()
        for link in links:
            sponsored_links.append(urljoin(response.url, link))
        return sponsored_links

    def _scrape_product_links(self, response):
        meta = response.meta.copy()
        prod_links = meta.get('prod_links', [])
        sponsored_links = meta.get('sponsored_links', [])
        ads = meta.get('ads', [])
        if not prod_links:
            prod_links = list(super(AmazonProductsSpider, self)._scrape_product_links(response))

        for (link, prod) in prod_links:
            if self.detect_ads and ads:
                prod['ads'] = ads
                prod['sponsored_links'] = sponsored_links
            yield link, prod

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        next_req = response.meta.get('next_page_link')
        if not next_req:
            next_link = super(AmazonProductsSpider, self)._scrape_next_results_page_link(response)
            return Request(
                url=urljoin(response.url, next_link),
                meta=meta
            )
        meta['next_page_link'] = None
        return next_req.replace(meta=meta)

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
                try:
                    d = datetime.strptime(date, '%b %d %Y')
                except ValueError as e:
                    self.log('Cant\'t parse date. ERROR: %s.' % str(e), WARNING)
                    d = None

            return d

        return None

    def _search_page_error(self, response):
        body = response.body_as_unicode()
        return "Your search" in body \
            and "did not match any products." in body

    @staticmethod
    def _get_reseller_id(link):
        reseller_id = re.search('dp/([A-Z\d]+)', link)
        return reseller_id.group(1) if reseller_id else None

    def is_nothing_found(self, response):
        txt = response.xpath('//h1[@id="noResultsTitle"]/text()').extract()
        txt = ''.join(txt)
        return 'did not match any products' in txt

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

        if not self.scrape_questions:
            if reqs:
                return self.send_next_request(reqs, response)
            else:
                return product

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
                if current_page < 5:
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
