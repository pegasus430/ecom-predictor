import traceback
import re

from datetime import datetime
from urlparse import urlparse, urljoin
from app.models import Review

from . import ReviewSpider, ReviewSpiderError


class ToysrusReview(Review):

    fields = Review.fields + ['verified']


class ToysrusReviewSpider(ReviewSpider):

    retailer = 'toysrus'

    review_class = ToysrusReview

    reviews_api_url = 'http://readservices-b2c.powerreviews.com/m/713039/l/en_US/product/{item_id}/reviews?sort=Newest'
    reviews_api_key = 'f0e82553-a1c6-41e1-826e-0a1b7436bd67'

    proxies = None  # don't use proxies

    def crawl(self, task):
        product_id = task['product_id']

        self.logger.info('Start crawl product {}'.format(product_id))

        product_url = task.get('product_url')
        if not product_url:
            product_url = 'https://www.toysrus.com/product?productId={}'.format(product_id)

        latest_date = self._get_latest_date(product_id)
        self.logger.info('Latest review date: {}'.format(latest_date))

        from_date = task.get('from_date')
        if from_date:
            self.logger.info('Do not crawl reviews older then {}'.format(from_date))

        try:
            item_id = self._parse_item_id(product_url)
            reviews_api_url = self.reviews_api_url.format(item_id=item_id)

            stop_crawler = False

            product_name = None

            while not stop_crawler:
                response = self._send_request('GET', reviews_api_url, headers={'Authorization': self.reviews_api_key})

                data = response.json()

                result = data['results'][0]

                if not product_name:
                    product_name = result.get('rollup', {}).get('name')

                for review_data in result['reviews']:
                    review = self.review_class(product_id=product_id, product_url=product_url,
                                               product_name=product_name)

                    review['date'] = datetime.fromtimestamp(review_data['details']['created_date'] / 1000)
                    review['rating'] = review_data['metrics']['rating']
                    review['author_name'] = review_data['details'].get('nickname') or ''
                    review['title'] = review_data['details'].get('headline') or ''
                    review['text'] = review_data['details'].get('comments') or ''
                    review['verified'] = review_data['badges']['is_verified_buyer']

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

                pagination = data['paging']

                if pagination.get('next_page_url'):
                    reviews_api_url = urljoin(reviews_api_url, pagination['next_page_url'])
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

        item_id = re.search(r'productId=(\d+)', url_parts.query)
        if item_id:
            return item_id.group(1)
        else:
            raise ReviewSpiderError('Can not parse item id from product url: {}'.format(product_url))
