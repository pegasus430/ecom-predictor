import copy
from operator import itemgetter
import re
import time
import traceback
from urllib import urlencode
from urlparse import urlparse

import dateparser

from . import ReviewSpider, ReviewSpiderError


class SamsclubCaReviewSpider(ReviewSpider):

    retailer = 'samsclub'

    reviews_api_params = {
        'apiversion': '5.5',
        'passkey': 'dap59bp2pkhr7ccd1hv23n39x',
        'filter': [
            'productid:eq:'
        ],
        'sort': 'submissiontime:desc',
        'include': 'comments',
        'limit': 100,
        'offset': 0
    }

    reviews_api_url = 'https://api.bazaarvoice.com/data/reviews.json?'
    product_api_url = 'https://api.bazaarvoice.com/data/products.json?apiversion=5.5&passkey=dap59bp2pkhr7ccd1hv23n39x&filter=id:'

    def crawl(self, task):
        product_id = task['product_id']

        self.logger.info('Start crawl product {}'.format(product_id))

        product_url = task.get('product_url')
        if not product_url:
            product_url = 'https://www.samsclub.com/sams/{}.ip'.format(product_id)

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

            reviews_api_params['filter'][-1] += item_id

            update_only = False
            stop_crawler = False
            try_count = 0

            while not stop_crawler:
                self.logger.info('Loading reviews page {}'.format(
                    (reviews_api_params['offset'] / reviews_api_params['limit']) + 1))
                response = self._send_request('GET', self.reviews_api_url + urlencode(reviews_api_params, True))

                try:
                    data = response.json()
                except:
                    self.logger.warn(traceback.format_exc())
                    self.logger.warn('Response: {}'.format(response.content))
                    data = {'Errors': [{'Message': 'Wrong json'}], 'HasErrors': True}

                if not data['HasErrors']:
                    if not data.get('Results'):
                        self.logger.info('No reviews: {}'.format(response.content))
                        break

                    try_count = 0

                    for review_data in data['Results']:
                        review = self.review_class(product_id=product_id, product_url=product_url,
                                                   product_name=product_name)

                        review['date'] = dateparser.parse(review_data['SubmissionTime']).replace(tzinfo=None)
                        review['rating'] = review_data['Rating']
                        review['author_name'] = review_data.get('UserNickname') or ''
                        review['title'] = review_data.get('Title') or ''
                        review['text'] = review_data.get('ReviewText') or ''
                        comments = []
                        for comment in review_data.get('ClientResponses') or []:
                            date = dateparser.parse(comment['Date']).replace(tzinfo=None)
                            comments.append((date, {
                                'date': date,
                                'author_name': comment.get('Department') or '',
                                'text': comment.get('Response') or ''
                            }))
                        for comment_id in review_data.get('CommentIds') or []:
                            try:
                                comment = review_data['Includes']['Comments'][comment_id]
                            except KeyError:
                                continue
                            else:
                                date = dateparser.parse(comment['SubmissionTime']).replace(tzinfo=None)
                                comments.append((date, {
                                    'date': date,
                                    'author_name': comment.get('UserNickname') or '',
                                    'title': comment.get('Title') or '',
                                    'text': comment.get('CommentText') or ''
                                }))
                        review['comments'] = [comment[1] for comment in sorted(comments, key=itemgetter(0), reverse=True)]
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

                    if data['Offset'] + data['Limit'] < data['TotalResults']:
                        reviews_api_params['offset'] += data['Limit']
                    else:
                        break
                else:
                    if try_count < self.max_retries:
                        try_count += 1

                        self.logger.warn('Repeat request because of Samsclub error: {}'.format(data['Errors']))
                        time.sleep(try_count)

                        continue

                    messages = []
                    for error in data['Errors']:
                        if 'Message' in error:
                            messages.append(error['Message'])
                    if messages:
                        message = ' '.join(messages)
                        raise ReviewSpiderError(message)
                    raise ReviewSpiderError(data['Errors'])
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

        item_id = re.search(r'/(\w+).ip$', url_parts.path)
        if item_id:
            return item_id.group(1)
        else:
            raise ReviewSpiderError('Can not parse item id from product url: {}'.format(product_url))

    def _parse_product_name(self, product_id):
        try_count = 0
        while try_count < self.max_retries:
            try_count += 1
            response = self._send_request('GET', self.product_api_url + product_id)

            try:
                data = response.json()
            except:
                self.logger.warn(traceback.format_exc())
                self.logger.warn('Response: {}'.format(response.content))
                continue

            return data.get('Results', [{}])[0].get('Name')
        else:
            raise ReviewSpiderError('Can not parse product name')
