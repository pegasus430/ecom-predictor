import dateutil.parser
import traceback
import re

from HTMLParser import HTMLParser
from urlparse import urlparse
from app.models import Review

from . import ReviewSpider, ReviewSpiderError


class TargetReview(Review):

    fields = Review.fields + ['verified', 'recommended', 'secondary_rating', 'source']


class TargetReviewSpider(ReviewSpider):

    retailer = 'target'

    proxies = None  # don't use proxies

    reviews_api_url = 'https://redsky.target.com/groot-domain-api/v1/reviews/{item_id}?sort=time_desc&filter=&limit=20&offset={offset}'
    product_api_url = 'http://redsky.target.com/v2/pdp/tcin/{item_id}'

    def crawl(self, task):
        product_id = task['product_id']

        self.logger.info('Start crawl product {}'.format(product_id))

        product_url = task.get('product_url')
        if not product_url:
            product_url = 'https://www.target.com/p/A-{}'.format(product_id)

        latest_date = self._get_latest_date(product_id)
        self.logger.info('Latest review date: {}'.format(latest_date))

        from_date = task.get('from_date')
        if from_date:
            self.logger.info('Do not crawl reviews older then {}'.format(from_date))

        try:
            item_id = self._parse_item_id(product_url)

            product_name = self._parse_product_name(item_id)

            offset = 0

            reviews_api_url = self.reviews_api_url.format(item_id=item_id, offset=offset)

            stop_crawler = False

            while not stop_crawler:
                response = self._send_request('GET', reviews_api_url)

                data = response.json()

                for review_data in data['result']:
                    review = self.review_class(product_id=product_id, product_url=product_url,
                                               product_name=product_name)

                    review['date'] = dateutil.parser.parse(review_data['SubmissionTime']).replace(tzinfo=None)
                    review['rating'] = review_data['Rating']
                    review['author_name'] = review_data.get('UserNickname') or ''
                    review['title'] = review_data.get('Title') or ''
                    review['text'] = review_data.get('ReviewText') or ''
                    review['verified'] = 'verifiedPurchaser' in (review_data.get('Badges') or {})
                    review['recommended'] = review_data.get('IsRecommended')
                    review['secondary_rating'] = dict(
                        (v.get('Label'), v.get('ValueLabel') or v.get('Value'))
                        for v in (review_data.get('SecondaryRatings') or {}).values()
                    )
                    review['source'] = review_data.get('SourceClient')

                    if from_date and review['date'] < from_date:
                        self.logger.info('Skip reviews older then {}. Stop crawler'.format(from_date))

                        stop_crawler = True
                        break

                    if latest_date:
                        if review['date'] == latest_date:
                            # skip scraped reviews to avoid duplicates
                            if self._check_duplicate(review):
                                self.logger.info('Skip duplicate: {}'.format(review))

                                continue
                        elif review['date'] < latest_date:
                            # don't scrape old reviews
                            self.logger.info('There are not new reviews. Stop crawler')

                            stop_crawler = True
                            break

                    self._save_review(review)

                offset += 20

                if offset < data.get('totalResults', 0) and data['result']:
                    reviews_api_url = self.reviews_api_url.format(item_id=item_id, offset=offset)
                else:
                    break
        except Exception as e:
            self.logger.error('Crawling error: {}, response: {}'.format(
                traceback.format_exc(),
                response.content if 'response' in locals() else None)
            )

            self.logger.info('Clear scraped reviews')
            self._clear_reviews(product_id, latest_date)

            error_message = e.message if isinstance(e, ReviewSpiderError) else 'Crawler error'

            raise ReviewSpiderError(error_message)
        else:
            self.logger.info('{} new reviews. Done'.format(self.reviews_counter))

    def _parse_item_id(self, product_url):
        url_parts = urlparse(product_url)

        item_id = re.search(r'/A-(\d+)', url_parts.path)
        if item_id:
            return item_id.group(1)
        else:
            raise ReviewSpiderError('Can not parse item id from product url: {}'.format(product_url))

    def _parse_product_name(self, item_id):
        response = self._send_request('GET', self.product_api_url.format(item_id=item_id)).json()

        title = response.get('product', {}).get('item', {}).get('product_description', {}).get('title')
        return HTMLParser().unescape(title)
