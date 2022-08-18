import re
import urlparse

from datetime import datetime

from scrapy.conf import settings
from scrapy.log import WARNING
from scrapy.http import Request

from product_ranking.utils import is_empty

from product_ranking.amazon_tests import AmazonTests
from product_ranking.amazon_base_class import AmazonBaseClass
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import FLOATING_POINT_RGEX


class AmazonProductsSpider(AmazonTests, AmazonBaseClass):
    name = 'amazones_products'
    allowed_domains = ["www.amazon.es"]
    SEARCH_URL = 'https://www.amazon.es/s/ref=nb_sb_noss?__mk_es_ES=%C3%85M%C3%85%C5%BD%C3%95%C3%91' \
                 '&url=search-alias%3Daps&field-keywords={search_term}'
    user_agent = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/61.0.3163.100 Safari/537.36')
    handle_httpstatus_list = [502, 503, 504]

    def __init__(self, *args, **kwargs):
        super(AmazonProductsSpider, self).__init__(*args, **kwargs)

        self.price_currency = 'EUR'
        self.price_currency_view = 'EUR'

        self.locale = 'es_ES'

        self.total_matches_re = '((\d+.?)+) resultados para'
        self.over_matches_re = r'de\s?([\d,.\s?]+)'

        self.avg_review_str = 'de 5 estrellas'
        self.num_of_reviews_re = r'Mostrando .+? de ([\d,\.]+) opiniones'
        self.all_reviews_link_xpath = '//div[@id="revSum" or @id="reviewSummary"]' \
                                      '//a[contains(text(), "Ver las")]/@href'

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def _format_last_br_date(self, date):
        """
        Parses date that is gotten from HTML.
        """
        months = {'enero': 'January',
                  'febrero': 'February',
                  'marzo': 'March',
                  'abril': 'April',
                  'mayo': 'May',
                  'junio': 'June',
                  'julio': 'July',
                  'agosto': 'August',
                  'septiembre': 'September',
                  'octubre': 'October',
                  'noviembre': 'November',
                  'diciembre': 'December'
                  }

        date = is_empty(
            re.findall(
                r'el (\d+ .+ \d+)',
                date
            )
        )

        if date:
            date = date.replace('de ', '')
            for key in months.keys():
                if key in date:
                    date = date.replace(key, months[key])
            try:
                d = datetime.strptime(date.replace('.', ''), '%d %B %Y')
                return d
            except ValueError as exc:
                self.log(
                    'Unable to parse last buyer review date: {exc}'.format(
                        exc=exc
                    ),
                    WARNING
                )

        return None

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
            total = response.xpath('.//*[contains(@class, "totalReviewCount")]/text()').re(FLOATING_POINT_RGEX)
            if not total:
                return ZERO_REVIEWS_VALUE
        if len(total) == 3:
            buyer_reviews['num_of_reviews'] = int(total[-1].replace(',', '').
                                                  replace('.', ''))
        else:
            buyer_reviews['num_of_reviews'] = int(total[0].replace(',', '').
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
        if not average:
            average = response.xpath(
                ".//*[contains(@class, 'reviewCountTextLinkedHistogram')]/@title"
            )
        try:
            average = re.sub(r'[%s]' % self.avg_review_str.encode('utf-8').decode('unicode_escape'),
                             '', average.extract()[0].encode('utf-8').decode('unicode_escape')) if average else 0.0
            buyer_reviews['average_rating'] = float(re.findall(r'\d+\.?\d*', average)[0])
        except:
            pass

        buyer_reviews['rating_by_star'] = {}
        variants = self._parse_variants(response)
        buyer_reviews, table = self.get_rating_by_star(response, buyer_reviews, variants)

        if not buyer_reviews.get('rating_by_star'):
            buyer_rev_link = is_empty(response.xpath(self.all_reviews_link_xpath).extract())
            buyer_rev_link = urlparse.urljoin(response.url, buyer_rev_link)
            if buyer_rev_link:
                buyer_rev_link = re.search(r'.*product-reviews/[a-zA-Z0-9]+/',
                                           buyer_rev_link)
                if buyer_rev_link:
                    buyer_rev_link = buyer_rev_link.group(0)
                    buyer_rev_req = Request(
                        url=buyer_rev_link,
                        callback=self.get_buyer_reviews_from_2nd_page)
                    return buyer_rev_req

        return BuyerReviews(**buyer_reviews)

    def _parse_no_longer_available(self, response):
        if response.xpath('//*[contains(@id, "availability")]'
                          '//*[contains(text(), "o disponible")]'):
            return True
        if response.xpath('//*[contains(@id, "outOfStock")]'
                          '//*[contains(text(), "o disponible")]'):
            return True
        if response.xpath('//*[contains(@class, "availRed")]'
                          '[contains(text(), "o disponible")]'):
            return True

    def _scrape_results_per_page(self, response):
        num = response.xpath(
            '//*[@id="s-result-count"]/text()').re('1 a (\d+) de')
        if num:
            return int(num[0])
        else:
            num = response.xpath(
                '//*[@id="s-result-count"]/text()').re('(\d+) resultados')
            if num:
                return int(num[0])