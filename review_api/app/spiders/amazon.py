import traceback
import json
import copy
from urlparse import urljoin, urlparse
from datetime import datetime

import re
import dateparser
from lxml import etree
from app.models import Review

from . import ReviewSpider, ReviewSpiderError


class AmazonReview(Review):

    fields = Review.fields + ['verified', 'variant']


class AmazonReviewSpider(ReviewSpider):

    retailer = 'amazon'

    review_class = AmazonReview

    comments_api_params = {
        'sortCommentsBy': 'oldest',
        'offset': 0,
        'count': 5,
        'pageIteration': 0,
        'asin': None,
        'reviewId': None,
        'nextPageToken': None,
        'scope': 'reviewsAjax0'
    }

    reviews_api_params = {
        'sortBy': 'recent',
        'reviewerType': 'all_reviews',
        'formatType': None,
        'mediaType': None,
        'filterByStar': None,
        'pageNumber': 1,
        'filterByKeyword': None,
        'shouldAppend': 'undefined',
        'deviceType': 'desktop',
        'reftag': 'cm_cr_arp_d_viewopt_srt',
        'pageSize': 10,
        'asin': None,
        'scope': 'reviewsAjax0'
    }

    host = 'www.amazon.com'
    user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:56.0) Gecko/20100101 Firefox/56.0'

    reviews_api_headers = {
        'Host': None,
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': user_agent
    }

    comments_api_url = 'https://{host}/ss/customer-reviews/ajax/comment/get/ref=cm_cr_arp_d_cmt_opn'

    reviews_api_url = 'https://{host}/ss/customer-reviews/ajax/reviews/get/ref=cm_cr_arp_d_viewopt_srt'

    proxies = {
        "proxy_out.contentanalyticsinc.com:60000": 3,
        "proxy_out.contentanalyticsinc.com:60001": 7
    }

    def __init__(self, *args, **kwargs):
        super(AmazonReviewSpider, self).__init__(*args, **kwargs)

        # depends on host
        self.reviews_api_headers['Host'] = self.host
        self.comments_api_url = self.comments_api_url.format(host=self.host)
        self.reviews_api_url = self.reviews_api_url.format(host=self.host)

    def _check_duplicate(self, review):
        return self.db[self.retailer].find_one({
            'product_id': review['product_id'],
            'date': review['date'],
            'url': review['url'],
            'author_name': review['author_name'],
            'title': review['title']
        })

    def crawl(self, task):
        product_id = task['product_id']

        self.logger.info('Start crawl product {}'.format(product_id))

        product_url = task.get('product_url')

        if not product_url:
            product_url = urljoin('https://{}/dp/'.format(self.host), product_id)
        else:
            if self.host not in product_url:
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

        try:
            product_name = self._parse_product_name(product_url)
        except:
            self.logger.warn(traceback.format_exc())
            self.logger.warn('Can not get product name')
            product_name = None

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
            reviews_api_params = copy.deepcopy(self.reviews_api_params)

            reviews_api_params['asin'] = product_id

            first_try_without_proxy = True
            update_only = False
            stop_crawler = False

            while not stop_crawler:
                self.logger.info('Loading reviews page {}'.format(reviews_api_params['pageNumber']))
                response = self._send_request('POST', self.reviews_api_url, data=reviews_api_params,
                                              headers=self.reviews_api_headers,
                                              first_try_without_proxy=first_try_without_proxy)

                try:
                    response_parts = filter(lambda part: part.strip(), re.split(r'(?<="])\s*&&&\s*(?=\["|$)',
                                                                                response.content))
                    response_data = map(lambda part: json.loads(part), response_parts)
                    append_data = filter(lambda data: data[0] == 'append', response_data)
                except:
                    if first_try_without_proxy:
                        self.logger.warn('Cannot get reviews data: {}, response: {}'.format(
                            traceback.format_exc(), response.content))
                        first_try_without_proxy = False
                        continue
                    else:
                        raise

                if not append_data:
                    self.logger.info('No reviews')
                    break

                for review_data in append_data[:-1]:
                    review = self.review_class(product_id=product_id, product_url=product_url,
                                               product_name=product_name)

                    review_html = etree.HTML(review_data[2])

                    review['date'] = self._parse_date(review_html)
                    review['url'] = self._parse_url(review_html)
                    review['rating'] = self._parse_rating(review_html)
                    review['author_name'], review['author_profile'] = self._parse_author(review_html)
                    review['title'] = self._parse_title(review_html)
                    review['text'] = self._parse_text(review_html)
                    review['verified'] = self._parse_verified(review_html)
                    review['variant'] = self._parse_variant(review_html)
                    review['comments_count'] = self._parse_comments_count(review_html)
                    review['comments'] = []

                    if from_date and review['date'] < from_date:
                        self.logger.info('Skip reviews older then {}. Stop crawler'.format(from_date))

                        stop_crawler = True
                        break

                    duplicate = None
                    new_comments = review['comments_count']
                    if latest_date:
                        if review['date'] < latest_date:
                            if not update_only:
                                # don't scrape old reviews
                                self.logger.info('There are not new reviews')
                                update_only = True
                            if not update_comments and not stop_crawler:
                                self.logger.info('Stop crawler')
                                stop_crawler = True
                        if review['date'] == latest_date or new_comments:
                            duplicate = self._check_duplicate(review)
                            if duplicate:
                                new_comments = review['comments_count'] > duplicate.get('comments_count', 0)
                            elif update_only:
                                continue

                    review_id = self._parse_review_id(review_html)
                    if not review_id:
                        self.logger.warn('Can not get review id')
                    elif new_comments:
                        review['comments'] = self.load_comments(product_id, review_id)
                        if review['comments_count'] < len(review['comments']):
                            review['comments_count'] = len(review['comments'])
                        elif review['comments_count'] > len(review['comments']):
                            self.logger.warn('Parsed comments count mismatch in review {}'.format(review_id))

                    if duplicate:
                        if not update_only:
                            # skip scraped reviews to avoid duplicates
                            self.logger.info('Skip duplicate: {}'.format(review))
                        if new_comments:
                            self.logger.debug('Updating comments for review {}'.format(review['url']))
                            self.db[self.retailer].update_one(
                                {'_id': duplicate['_id']},
                                {'$set': {'comments_count': review['comments_count'], 'comments': review['comments']}})
                    elif not update_only:
                        self._save_review(review)

                pagination_data = append_data[-1]

                if pagination_data[2]:
                    pagination_html = etree.HTML(pagination_data[2])

                    if self._parse_next_page(pagination_html):
                        reviews_api_params['pageNumber'] += 1
                        first_try_without_proxy = True
                        continue

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
            if update_comments:
                self._set_comments_update(product_id)
            self.logger.info('{} new reviews. Done'.format(self.reviews_counter))

    def load_comments(self, product_id, review_id):
        comments = []

        comments_api_params = copy.deepcopy(self.comments_api_params)
        comments_api_params['asin'] = product_id
        comments_api_params['reviewId'] = review_id

        first_try_without_proxy = True
        while True:
            self.logger.info('Loading comments page {}'.format(comments_api_params['pageIteration'] + 1))
            response = self._send_request('POST', self.comments_api_url, data=comments_api_params,
                                          headers=self.reviews_api_headers,
                                          first_try_without_proxy=first_try_without_proxy)

            try:
                response_parts = filter(lambda part: part.strip(), re.split(r'(?<="])\s*&&&\s*(?=\["|$)',
                                                                            response.content))
                response_data = map(lambda part: json.loads(part), response_parts)
                append_data = filter(lambda data: data[0] == 'appendFadeIn', response_data)
            except:
                if first_try_without_proxy:
                    self.logger.warn('Cannot get comments data: {}, response: {}'.format(
                        traceback.format_exc(), response.content))
                    first_try_without_proxy = False
                    continue
                else:
                    raise

            if len(append_data) <= 1:
                self.logger.info('No comments')
                break

            next_page_token = None
            for comment_data in append_data[:-1]:
                comment = {}
                comment_html = etree.HTML(comment_data[2])

                comment['date'] = self._parse_comment_date(comment_html)
                comment['author_name'], comment['author_profile'] = self._parse_author(comment_html)
                comment['text'] = self._parse_comment_text(comment_html)
                next_page_token = self._parse_comment_next_page_token(comment_html)

                comments.append(comment)

            if next_page_token:
                comments_api_params['pageIteration'] += 1
                comments_api_params['offset'] += comments_api_params['count']
                comments_api_params['nextPageToken'] = next_page_token
                first_try_without_proxy = True
                continue

            break
        return comments

    def _parse_comment_date(self, comment_html):
        date = comment_html.xpath(".//span[contains(@class,'comment-time-stamp')]/text()")
        if date:
            return dateparser.parse(date[0])

    def _parse_comment_text(self, comment_html):
        text = comment_html.xpath(".//span[@class='review-comment-text']/text()")
        if text:
            return '\n'.join(part.strip() for part in text)

    def _parse_comment_next_page_token(self, comment_html):
        for param in comment_html.xpath(".//*[@data-reviews-state-param]/@data-reviews-state-param"):
            try:
                return json.loads(param)['nextPageToken']
            except:
                pass

    def _parse_comments_count(self, review_html):
        count = review_html.xpath(".//span[contains(@class,'review-comment-total')]/text()")
        if count:
            try:
                return int(count[0])
            except:
                pass

    def _parse_review_id(self, review_html):
        review_id = review_html.xpath(".//*[@data-hook='review']/@id")
        if review_id:
            return review_id[0]

    def _parse_date(self, review_html):
        date = review_html.xpath(".//*[@data-hook='review-date']/text()")
        if date:
            return datetime.strptime(date[0], 'on %B %d, %Y')

    def _parse_rating(self, review_html):
        rating = review_html.xpath(".//*[@data-hook='review-star-rating']/span/text()")
        if rating:
            stars = re.match(r'(\d)\.0', rating[0])
            if stars:
                return int(stars.group(1))

    def _parse_author(self, review_html):
        name = None
        profile = None

        author = review_html.xpath(".//a[@data-hook='review-author']")
        if author:
            author_name = author[0].xpath("text()")
            if author_name:
                name = author_name[0]

            author_profile = author[0].xpath("@href")
            if author_profile:
                profile = urljoin('https://{}'.format(self.host), author_profile[0])

        return name, profile

    def _parse_title(self, review_html):
        title = review_html.xpath(".//*[@data-hook='review-title']/text()")
        if title:
            return title[0]

    def _parse_text(self, review_html):
        text = review_html.xpath(".//*[@data-hook='review-body']/text()")
        if text:
            return '\n'.join(text)

    def _parse_verified(self, review_html):
        verified = review_html.xpath(".//*[@data-hook='avp-badge']")

        return bool(verified)

    def _parse_url(self, review_html):
        url = review_html.xpath(".//*[@data-hook='review-title']/@href")
        if url:
            return urljoin('https://{}'.format(self.host), url[0])

    def _parse_next_page(self, pagination_html):
        next_page = pagination_html.xpath(".//li[contains(@class,'a-last')]/a")

        return bool(next_page)

    def _parse_product_name(self, product_url):
        response = self._send_request('GET', product_url, headers={
            'Host': self.host,
            'User-Agent': self.user_agent
        }, first_try_without_proxy=True)

        html = etree.HTML(response.content)

        product_name = html.xpath('.//*[@id="productTitle"]/text()')
        if product_name:
            return product_name[0].strip()

    def _parse_variant(self, review_html):
        variant = review_html.xpath('.//*[@data-hook="format-strip"]/text()')

        if variant:
            return [{'name': name.strip(), 'value': value.strip()}
                    for name, value in (v.split(':', 1) for v in variant)]

    @staticmethod
    def get_product_id_from_url(product_url):
        for path_part in reversed(urlparse(product_url).path.split('/')):
            if path_part and re.match(r'^[\w\d]+$', path_part):
                return path_part
