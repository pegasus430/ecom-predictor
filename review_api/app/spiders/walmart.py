import traceback
import copy
from datetime import datetime
from urlparse import urlparse, urljoin

import re
import time

from . import ReviewSpider, ReviewSpiderError


class WalmartReviewSpider(ReviewSpider):

    retailer = 'walmart'

    reviews_api_params = {
        'itemId': None,
        'paginationContext': {
            'page': 1,
            'sort': 'submission-desc',
            'filters': [],
            'limit': 100
        }
    }

    reviews_api_url = 'https://www.walmart.com/terra-firma/fetch?rgs=REVIEWS_MAP'
    product_api_url = 'https://www.walmart.com/terra-firma/item/'

    def crawl(self, task):
        product_id = task['product_id']

        self.logger.info('Start crawl product {}'.format(product_id))

        product_url = task.get('product_url')
        if not product_url:
            product_url = urljoin('https://www.walmart.com/ip/', product_id)
        else:
            if 'www.walmart.com' not in product_url:
                url_parts = urlparse(product_url)
                domain_zone = url_parts.netloc.split('.')[-1]
                retailer = self.retailer.split('_')[0]
                if domain_zone != 'com':
                    retailer = '{}_{}'.format(retailer, domain_zone)

                if retailer != self.retailer:
                    self.logger.warn('Wrong retailer "{}": for url {} it must be {}'.format(
                        self.retailer, product_url, retailer))

                    self.db.tasks.update_one({'_id': task['_id']},
                                             {'$set': {'started_at': None, 'retailer': retailer}})
                    if task.get('daily') or task.get('daily_frequency'):
                        self.db.daily_tasks.update_one(
                            {'retailer': self.retailer, 'product_id': product_id, 'server': task.get('server')},
                            {'$set': {'retailer': retailer}})
                    return

        latest_date = self._get_latest_date(product_id)
        self.logger.info('Latest review date: {}'.format(latest_date))

        update_comments = self._check_comments_update(product_id, latest_date)
        self.logger.info('Update comments: {}'.format(update_comments))

        from_date = task.get('from_date')
        if from_date:
            self.logger.info('Do not crawl reviews older then {}'.format(from_date))
        elif latest_date and update_comments:
            from_date = self._get_first_date(product_id)
            self.logger.info('First review date: {}'.format(from_date))

        try:
            item_id = self._parse_item_id(product_url)

            product_name = self._parse_product_name(item_id)

            reviews_api_params = copy.deepcopy(self.reviews_api_params)

            reviews_api_params['itemId'] = item_id

            update_only = False
            stop_crawler = False
            reversed_limit = 0
            total = 0
            try_count = 0

            while not stop_crawler:
                self.logger.info('Loading reviews page {}'.format(reviews_api_params['paginationContext']['page']))
                response = self._send_request('POST', self.reviews_api_url, json=reviews_api_params)

                try:
                    data = response.json()
                except:
                    self.logger.warn(traceback.format_exc())
                    self.logger.warn('Response: {}'.format(response.content))
                    data = {'errors': 'Wrong json', 'status': 'error'}

                if data['status'] == 'OK':
                    reviews_data = data['payload']['reviews'].values()[0]

                    response_total = reviews_data['pagination']['total']

                    if not reviews_data.get('customerReviews'):
                        if response_total < total and try_count < self.max_retries:
                            self.logger.warn('Repeat request because current total {} < previous total {}'.format(
                                response_total, total))

                            time.sleep(10 + try_count)

                            try_count += 1

                            continue

                        if response_total and not reversed_limit and try_count < self.max_retries:
                            last = int(reviews_data['pagination']['currentSpan'].split('-')[0]) - 1
                            reversed_limit = response_total - last
                            if reversed_limit:
                                reviews_api_params['paginationContext']['sort'] = 'submission-asc'
                                reviews_api_params['paginationContext']['page'] = 1
                                self.logger.warn('No reviews in response. Changing order to get the last {} items'.format(
                                    reversed_limit))
                                continue

                        self.logger.info('No reviews: {}'.format(response.content))
                        break

                    try_count = 0
                    total = response_total

                    if reversed_limit:
                        reviews_data['customerReviews'] = reviews_data['customerReviews'][:reversed_limit]
                        reviews_data['customerReviews'].reverse()

                    for review_data in reviews_data['customerReviews']:
                        review = self.review_class(product_id=product_id, product_url=product_url,
                                                   product_name=product_name)

                        review['date'] = datetime.strptime(review_data['reviewSubmissionTime'], '%m/%d/%Y')
                        review['rating'] = review_data.get('rating')
                        review['author_name'] = review_data.get('userNickname') or ''
                        review['title'] = review_data.get('reviewTitle') or ''
                        review['text'] = review_data.get('reviewText') or ''
                        review['comments'] = []
                        for comment in review_data.get('clientResponses') or []:
                            review['comments'].append({
                                'date': datetime.strptime(comment['date'], '%m/%d/%Y'),
                                'author_name': comment.get('department') or '',
                                'text': comment.get('response') or ''
                            })
                        review['comments_count'] = len(review['comments'])

                        if from_date and review['date'] < from_date:
                            self.logger.info('Skip reviews older then {}. Stop crawler'.format(from_date))

                            stop_crawler = True
                            break

                        if latest_date:
                            if review['date'] < latest_date:
                                if not update_only:
                                    # don't scrape old reviews
                                    self.logger.info('There are not new reviews')
                                    update_only = True
                                if not update_comments and not stop_crawler:
                                    self.logger.info('Stop crawler')
                                    stop_crawler = True
                            if review['date'] == latest_date or review['comments_count']:
                                duplicate = self._check_duplicate(review)
                                if duplicate:
                                    if not update_only:
                                        # skip scraped reviews to avoid duplicates
                                        self.logger.info('Skip duplicate: {}'.format(review))
                                    if review['comments_count'] > duplicate.get('comments_count', 0):
                                        self.logger.debug('Updating comments for review from {}'.format(review['date']))
                                        self.db[self.retailer].update_one(
                                            {'_id': duplicate['_id']},
                                            {'$set': {
                                                'comments_count': review['comments_count'],
                                                'comments': review['comments']}
                                            })
                                    continue

                        if not update_only:
                            self._save_review(review)

                    if reversed_limit:
                        reversed_limit -= reviews_api_params['paginationContext']['limit']
                        if reversed_limit <= 0:
                            break

                    pagination = reviews_data['pagination']

                    if pagination.get('next'):
                        reviews_api_params['paginationContext']['page'] += 1
                    else:
                        break
                else:
                    if try_count < self.max_retries:
                        try_count += 1

                        self.logger.warn('Repeat request because of Walmart error: {}'.format(data['errors']))
                        time.sleep(try_count)

                        continue

                    try:
                        error = data['errors'][0]['errorIdentifiers']['entry'][0]['value']
                    except:
                        pass
                    else:
                        if error.get('code', '').startswith('404'):
                            message = error.get('description')
                            if message:
                                raise ReviewSpiderError(message)
                    raise ReviewSpiderError(data['errors'])
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
            if update_comments:
                self._set_comments_update(product_id)
            self.logger.info('{} new reviews. Done'.format(self.reviews_counter))

    def _parse_item_id(self, product_url):
        url_parts = urlparse(product_url)

        item_id = re.search(r'/(\d{3,20})', url_parts.path)
        if item_id:
            return item_id.group(1)
        else:
            raise ReviewSpiderError('Can not parse item id from product url: {}'.format(product_url))

    def _parse_product_name(self, product_id):
        try_count = 0
        while try_count < self.max_retries:
            try_count += 1
            response = self._send_request('GET', urljoin(self.product_api_url, product_id))

            try:
                data = response.json()
            except:
                self.logger.warn(traceback.format_exc())
                self.logger.warn('Response: {}'.format(response.content))
                continue

            product = data.get('payload', {}).get('selected', {}).get('product')
            if product:
                return data.get('payload', {}).get('products', {}).get(
                    product, {}).get('productAttributes', {}).get('productName')
            break
        else:
            raise ReviewSpiderError('Can not parse product name')

    @staticmethod
    def get_product_id_from_url(product_url):
        product_id = re.findall(r'/([0-9]{3,20})', product_url)

        if not product_id:
            product_id = urlparse(product_url).path.split('/')

        return product_id[-1] if product_id else None
