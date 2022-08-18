import traceback

import re
import json
from itertools import izip
from datetime import datetime

from scrapy import Selector
from scrapy.log import ERROR, WARNING
import lxml.html

from product_ranking.items import BuyerReviews


is_empty = lambda x, y=None: x[0] if x else y


class BuyerReviewsBazaarApi(object):
    def __init__(self, *args, **kwargs):
        self.called_class = kwargs.get('called_class')

        self.ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

    def parse_buyer_reviews_products_json(self, response):
        meta = response.meta.copy()
        product = meta['product']
        try:
            json_data = json.loads(response.body_as_unicode())
            product_reviews = json_data["Results"][0].get('ReviewStatistics',{})
            if product_reviews:
                rating_by_stars = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}

                for rating_distribution in product_reviews.get('RatingDistribution',[]):
                    rating_by_stars[str(rating_distribution['RatingValue'])] = rating_distribution['Count']

                if product_reviews.get('LastSubmissionTime', False):
                    last_buyer_review_date = product_reviews.get('LastSubmissionTime').split('.')[0]
                    product[u'last_buyer_review_date'] = datetime.strptime(last_buyer_review_date, "%Y-%m-%dT%H:%M:%S").strftime('%d-%m-%Y')

                average_rating = product_reviews.get('AverageOverallRating', 0)
                if not isinstance(average_rating, float):
                    try:
                        average_rating = float(average_rating)
                    except:
                        average_rating = 0.0

                return {'num_of_reviews': product_reviews.get('TotalReviewCount',0),
                        'average_rating': round(average_rating, 1),
                        'rating_by_star': rating_by_stars
                }

        except ValueError:
            self.called_class.log('Response not a json format', ERROR)

        except Exception as e:
            self.called_class.log(e, ERROR)

        return self.ZERO_REVIEWS_VALUE

    def parse_buyer_reviews_single_product_json(self, response):
        """
        Parses all buyer reviews from bazaarvoice API for single product by one requests
        Please check: https://developer.bazaarvoice.com/conversations-api/reference/v5.4/reviews/review-display
        Request url: http://api.bazaarvoice.com/data/reviews.json?apiversion=5.4
                     &passkey={passkey}&Filter=ProductId:{product_id}&Include=Products&Stats=Reviews
        Requires response.meta['product_id'] which passed to request url
        :param response:
        :return dict:
        """
        meta = response.meta.copy()
        product_id = meta['product_id']
        if product_id:
            try:
                json_data = json.loads(response.body, encoding='utf-8')
                product_reviews_stats = json_data.get('Includes', {})\
                    .get('Products', {})\
                    .get(product_id, {})\
                    .get('ReviewStatistics', None)
                if product_reviews_stats:
                    rating_by_stars = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
                    for rating in product_reviews_stats.get('RatingDistribution', []):
                        rating_value = str(rating.get('RatingValue', ''))
                        if rating_value in rating_by_stars.keys():
                            rating_by_stars[rating_value] = int(rating.get('Count', 0))
                    return {
                        'num_of_reviews': int(product_reviews_stats.get('TotalReviewCount', 0)),
                        'average_rating': float(product_reviews_stats.get('AverageOverallRating', .0)),
                        'rating_by_star': rating_by_stars,
                    }

            except Exception as e:
                self.called_class.log(e, ERROR)

        return self.ZERO_REVIEWS_VALUE

    def parse_buyer_reviews_per_page(self, response, body_data=None,
                                     get_rating_by_star_method=None, get_last_buyer_review_date_method=None):
        """
        return dict for buyer_reviews
        """
        meta = response.meta.copy()
        product = meta['product']
        reqs = meta.get('reqs', [])

        if body_data is None:
            body_data = response.body_as_unicode()

        # Get dictionary for BR analytics data from response body
        base_reviews_data = is_empty(
            re.findall(
                r'webAnalyticsConfig:({.+})',
                body_data
            )
        )
        if base_reviews_data:
            try:
                base_reviews_data = json.loads(base_reviews_data)
                base_reviews_data = base_reviews_data['jsonData']
                num_of_reviews = int(
                    base_reviews_data['attributes']['numReviews']
                )

                if num_of_reviews:
                    average_rating = base_reviews_data['attributes']['avgRating']

                    # It is good idea to have a possibility override some methods
                    if callable(get_rating_by_star_method):
                        rating_by_star = get_rating_by_star_method(response)
                    else:
                        rating_by_star = self.get_rating_by_star(response)

                    # Also this method too. If None, will used default hardcoded in the get_rating_by_star method
                    if callable(get_last_buyer_review_date_method):
                        get_last_buyer_review_date_method(response)

                    buyer_reviews = {
                        'num_of_reviews': num_of_reviews,
                        'average_rating': round(average_rating, 1),
                        'rating_by_star': rating_by_star
                    }
                else:
                    buyer_reviews = self.ZERO_REVIEWS_VALUE

            except (KeyError, IndexError) as exc:
                self.called_class.log(
                    'Unable to parse buyer reviews on {url}: {exc}'.format(
                        url=product['url'],
                        exc=exc
                    ), ERROR
                )
                buyer_reviews = self.ZERO_REVIEWS_VALUE
        else:
            if callable(get_rating_by_star_method):
                rating_by_star = get_rating_by_star_method(response)
            else:
                rating_by_star = self.get_rating_by_star(response)

            if callable(get_last_buyer_review_date_method):
                get_last_buyer_review_date_method(response)

            if rating_by_star:
                num_of_reviews = response.xpath(
                    '//*[contains(@class, "BVRRCount")]/*[contains(@class, "BVRRNumber")]/text()').extract()
                average_rating = response.xpath(
                    '//*[contains(@class, "BVRRSReviewsSummaryOutOf")]/*[contains(@class, "BVRRNumber")]/text()'
                ).extract()
                if num_of_reviews and average_rating:
                    invalid_reviews = False
                    try:
                        num_of_reviews = int(num_of_reviews[0])
                        average_rating = float(average_rating[0])
                    except Exception as e:
                        print('Invalid reviews: [%s] at %s' % (str(e), response.url))
                        invalid_reviews = True
                    if not invalid_reviews:
                        buyer_reviews = {
                            'num_of_reviews': num_of_reviews,
                            'average_rating': round(average_rating, 1),
                            'rating_by_star': rating_by_star
                        }
                        return buyer_reviews
            buyer_reviews = self.ZERO_REVIEWS_VALUE

        return buyer_reviews

    def parse_buyer_reviews(self, response):
        """
        Parses buyer reviews from bazaarvoice API
        Create object from dict
        :param response:
        :return:
        """
        meta = response.meta.copy()
        product = meta['product']
        reqs = meta.get('reqs', [])

        product['buyer_reviews'] = BuyerReviews(**self.parse_buyer_reviews_per_page(response))

        yield product
        if reqs:
            yield self.called_class.send_next_request(reqs, response)

    @staticmethod
    def _scrape_alternative_rating_by_star(response):
        rating_by_star = {}
        for i in xrange(1, 6):
            num_reviews = response.xpath(
                '//*[contains(@class, "BVRRHistogramContent")]//*[contains(@class, "BVRRHistogramBarRow%i")]'
                '/*[contains(@class, "BVRRHistAbsLabel")]//text()' % i).extract()
            if num_reviews:
                num_reviews = int(num_reviews[0])
                rating_by_star[str(i)] = num_reviews
        return rating_by_star

    def get_rating_by_star(self, response):
        meta = response.meta.copy()
        product = meta['product']

        data = is_empty(
            re.findall(
                r'materials=({.+})',
                response.body_as_unicode()
            )
        )
        if data:
            try:
                data = json.loads(data)
                histogram_data = data['BVRRSourceID'].replace('\\ ', '')\
                    .replace('\\', '').replace('\\"', '')
                dates = re.findall(
                    r'<span class="BVRRValue BVRRReviewDate">(\d+ \w+ \d+).+</span>',
                    histogram_data
                )

                if not dates:
                    dates = re.findall(
                        r'<span class=\"BVRRValue BVRRReviewDate\">(\w+ \d+. \d+)',
                        histogram_data
                    )

                new_dates = []
                if dates:
                    for date in dates:
                        if product.get('locale'):
                            months = self._format_br_date(product['locale'])
                            for key in months.keys():
                                if key in date:
                                    date = date.replace(key, months[key])
                        try:
                            new_date = datetime.strptime(date.replace('.', '').replace(',', ''), '%d %B %Y')
                        except:
                            try:
                                new_date = datetime.strptime(date.replace('.', '').replace(',', ''), '%B %d %Y')
                            except:
                                new_date = datetime.strptime(date.replace('.', '').replace(',', ''), '%b %d %Y')
                        new_dates.append(new_date)

                if new_dates:
                    product['last_buyer_review_date'] = max(new_dates).strftime(
                        '%d-%m-%Y')
                bystars_regex = '<span class="BVRRHistStarLabelText">(\d+) (?:S|s)tars?</span>|' \
                                '<span class="BVRRHistAbsLabel">([0-9 ,]+)'

                stars_data = re.findall(bystars_regex, histogram_data)
                if not stars_data:
                    histogram_data = response.body_as_unicode().replace('\\ ', '').replace('\\', '').replace('\\"', '')
                    stars_data = re.findall(bystars_regex, histogram_data)
                if stars_data:
                    # ('5', '') --> '5'
                    item_list = []
                    for star in stars_data:
                        item_list.append(filter(None, list(star))[0])

                    # ['3', '0', '5', '6'] --> {'3': '0', '5': '6'}
                    i = iter(item_list)
                    stars = {k: int(v.replace(',','')) for (k, v) in izip(i, i)}
                else:
                    stars_data = re.findall(
                        r'<div itemprop="reviewRating".+>.+<span itemprop="ratingValue" '
                        r'class="BVRRNumber BVRRRatingNumber">(\d+)</span>|'
                        r'<span itemprop=\"ratingValue\" class=\"BVRRNumber BVRRRatingNumber\">(\d+).\d+',
                        histogram_data
                    )
                    stars_data = [x for i in stars_data for x in i if x != '']
                    stars = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
                    for star in stars_data:
                        stars[star] += 1

                    # check if stars values == br_count
                    if hasattr(self, 'br_count'):
                        result = {}
                        if self.br_count != sum([k for k in stars.values()]):
                            lxml_doc = lxml.html.fromstring(data.get('BVRRRatingSummarySourceID', ''))
                            for stars_num in range(1, 6):
                                stars_element = lxml_doc.xpath(
                                    '//*[contains(@class, "BVRRHistogramBarRow")]'
                                    '[contains(@class, "BVRRHistogramBarRow%s")]' % stars_num)
                                if stars_element:
                                    num_reviews = re.search(r'\((\d+)\)', stars_element[0].text_content())
                                    if num_reviews:
                                        num_reviews = num_reviews.group(1)
                                        result[str(stars_num)] = int(num_reviews)
                            return result
                return stars

            except (KeyError, IndexError) as exc:
                self.called_class.log(
                    'Unable to parse buyer reviews on {url}: {exc}'.format(
                        url=product['url'],
                        exc=exc
                    ), ERROR
                )
                return self.ZERO_REVIEWS_VALUE['rating_by_star']
        else:
            if not data:
                # try to scrape alternative rating by star data
                alternative_rating_by_star = self._scrape_alternative_rating_by_star(response)
                if alternative_rating_by_star:
                    return alternative_rating_by_star
            return self.ZERO_REVIEWS_VALUE['rating_by_star']

    # TODO: Need to re-write class for flexible overriding and implementing special cases

    # You can try to use this, if everything above not parsing correct
    def one_more_parse_buyer_reviews(self, response):
        meta = response.meta.copy()
        product = meta['product']
        product['buyer_reviews'] = BuyerReviews(**self.parse_buyer_reviews_per_page(
            response=response,
            get_rating_by_star_method=self.one_more_get_rating_by_star,
            get_last_buyer_review_date_method=self.one_more_get_last_buyer_review_date
        ))
        return product

    def _format_br_date(self, locale):
        months = {}
        if locale == 'fr_FR':
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
        if locale == 'de_DE':
            months = {'Januar': 'January',
                      'Februar': 'February',
                      u'M\xe4rz': 'March',
                      'Mai': 'May',
                      'Juni': 'June',
                      'Juli': 'July',
                      'Oktober': 'October',
                      'Dezember': 'December'
                      }
        return months

    def one_more_get_last_buyer_review_date(self, response):
        def get_date_by_formats(date, formats):
            for f in formats:
                try:
                    return datetime.strptime(date.replace('.', '').replace(',', ''), f)
                except:
                    pass

        product = response.meta['product']

        data = re.search(r'materials=({.+})', response.body_as_unicode())
        if data:
            try:
                review_dates = []
                data = json.loads(data.group(1))
                histogram_data = data.get('BVRRSourceID', None)
                if histogram_data:
                    dates = Selector(text=histogram_data).xpath(
                        '//*[contains(@class, "BVRRValue")]'
                        '[contains(@class, "BVRRReviewDate")]'
                        '/text()'
                    )
                    review_dates.extend(dates.re(r'(\d+ \w+ \d+).+'))
                    review_dates.extend(dates.re(r'(\w+ \d+. \d+)'))

                    date_formats = [
                        '%d %B %Y',
                        '%B %d %Y',
                        '%b %d %Y',
                    ]

                    review_dates = [get_date_by_formats(review_date, date_formats) for review_date in review_dates]
                    if review_dates:
                        product['last_buyer_review_date'] = max(review_dates).strftime('%d-%m-%Y')
            except:
                self.called_class.log(
                    traceback.format_exc(),
                    level=WARNING
                )

    def one_more_get_rating_by_star(self, response):
        data = re.search(r'materials=({.+})', response.body_as_unicode())
        if data:
            try:
                stars = {}
                data = json.loads(data.group(1))
                histogram_data = data.get('BVRRSourceID', None)
                if histogram_data:
                    labels = Selector(text=histogram_data).xpath(
                        '//*[contains(@class, "BVRRHistStarLabelText")]'
                        '/text()'
                    ).re(r'(\d+)')
                    values = Selector(text=histogram_data).xpath(
                        '//*[contains(@class, "BVRRHistAbsLabel")]'
                        '/text()'
                    ).re(r'(\d+)')
                    if labels and values:
                        for label, value in zip(labels, values):
                            stars.update({
                                label: int(value)
                            })
                        return stars
            except:
                self.called_class.log(
                    traceback.format_exc(),
                    level=WARNING
                )

    def _parse_buyer_reviews_from_filters(self, response):
        product = response.meta['product']

        buyer_review_values = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            review_json = json.loads(response.body)
            if 'FilteredReviewStatistics' in review_json["BatchedResults"]["q0"]["Results"][0]:
                review_statistics = review_json["BatchedResults"]["q0"]["Results"][0]['FilteredReviewStatistics']
            else:
                review_statistics = review_json["BatchedResults"]["q0"]["Results"][0]['ReviewStatistics']

            if review_statistics.get("RatingDistribution"):
                for item in review_statistics['RatingDistribution']:
                    key = str(item['RatingValue'])
                    buyer_review_values["rating_by_star"][key] = item['Count']

            if review_statistics.get("TotalReviewCount"):
                buyer_review_values["num_of_reviews"] = review_statistics["TotalReviewCount"]

            if review_statistics.get("AverageOverallRating"):
                buyer_review_values["average_rating"] = format(review_statistics["AverageOverallRating"], '.1f')
        except Exception as e:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), ERROR)
        finally:
            buyer_reviews = BuyerReviews(**buyer_review_values)
            product['buyer_reviews'] = buyer_reviews
            return product