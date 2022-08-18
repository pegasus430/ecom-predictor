from datetime import datetime
from datetime import timedelta
from collections import defaultdict
import inspect
import logging
import time
from importlib import import_module
from pkgutil import iter_modules
import random
import re
import traceback

import requests
import os
from bson.code import Code
from pymongo import ASCENDING
from pymongo import DESCENDING
from app.models import Review


def load_spiders(path):

    def walk_modules(path):
        mods = []
        mod = import_module(path)
        mods.append(mod)
        if hasattr(mod, '__path__'):
            for _, subpath, ispkg in iter_modules(mod.__path__):
                fullpath = path + '.' + subpath
                if ispkg:
                    mods += walk_modules(fullpath)
                else:
                    submod = import_module(fullpath)
                    mods.append(submod)
        return mods

    spiders = {}

    for module in walk_modules(path):
        for obj in vars(module).itervalues():
            if inspect.isclass(obj)\
                    and issubclass(obj, ReviewSpider)\
                    and obj.__module__ == module.__name__\
                    and getattr(obj, 'retailer', None):
                spiders[obj.retailer] = obj

    return spiders


class ReviewSpiderError(Exception):
    pass


class ReviewSpider(object):

    retailer = None

    max_retries = 15

    review_class = Review

    proxies = {
        'proxy_out.contentanalyticsinc.com:60002': 1,
        'proxy_out.contentanalyticsinc.com:60000': 3,
        'proxy_out.contentanalyticsinc.com:60001': 6
    }

    stop_words = {'about', 'above', 'after', 'again', 'against', 'all', 'also',
                  'and', 'any', 'are', 'aren', 'because', 'been', 'before',
                  'being', 'below', 'between', 'both', 'but', 'can', 'cannot',
                  'could', 'couldn', 'did', 'didn', 'does', 'doesn', 'doing',
                  'don', 'down', 'during', 'each', 'etc', 'few', 'for', 'from',
                  'further', 'had', 'hadn', 'has', 'hasn', 'have', 'haven',
                  'having', 'her', 'here', 'hers', 'herself', 'him', 'himself',
                  'his', 'how', 'into', 'isn', 'its', 'itself', 'let', 'more',
                  'most', 'mustn', 'myself', 'nor', 'not', 'off', 'once',
                  'only', 'other', 'ought', 'our', 'ours', 'ourselves', 'out',
                  'over', 'own', 'same', 'shan', 'she', 'should', 'shouldn',
                  'some', 'stars', 'such', 'than', 'that', 'the', 'their',
                  'theirs', 'them', 'themselves', 'then', 'there', 'these',
                  'they', 'this', 'those', 'through', 'too', 'under', 'until',
                  'very', 'was', 'wasn', 'were', 'weren', 'what', 'when',
                  'where', 'which', 'while', 'who', 'whom', 'why', 'with',
                  'would', 'wouldn', 'you', 'your', 'yours', 'yourself',
                  'yourselves'}

    def __init__(self, task_id, resources_dir, database, logger=None):
        self.task_id = task_id
        self._resources_dir = os.path.join(resources_dir,  self.task_id)

        if not os.path.exists(self._resources_dir):
            os.makedirs(self._resources_dir)

        self.logger = self._add_log_file(logger or logging.getLogger(__name__))
        self.db = database
        self.first_review_id = None
        self.latest_review_date = None
        self.reviews_counter = 0
        self.reviews_by_rating_counter = defaultdict(int)

    def _add_log_file(self, logger):
        child_logger = logger.getChild(self.task_id)

        log_path = os.path.join(self._resources_dir, 'task.log')

        log_format = logging.Formatter('%(asctime)s %(levelname)s:{request_id}:%(message)s'.format(
            request_id=self.task_id))
        log_format.datefmt = '%Y-%m-%d %H:%M:%S'

        log_file = logging.FileHandler(log_path)
        log_file.setFormatter(log_format)
        log_file.setLevel(logging.INFO)
        child_logger.addHandler(log_file)

        return child_logger

    def close_log_file(self):
        for handler in self.logger.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                handler.close()
                self.logger.removeHandler(handler)

    def update_words_collection(self, product_id, force_update=False):
        collection = 'words_%s' % self.retailer
        query = {'product_id': product_id}
        if self.first_review_id:
            query['_id'] = {'$gte': self.first_review_id}
            if self.latest_review_date is None:
                self._get_latest_date(product_id)
        else:
            if not force_update:
                return
            self.db[collection].delete_many({'_id.product_id': product_id})

        reduce = Code('''function (key, values) {
            var result = {};
            values.forEach(function (value) {
                if (Array.isArray(value)) {
                    value.forEach(function (word) {
                        if (!result[word.w]) {
                            result[word.w] = {positive: 0, negative: 0};
                        }
                        if (word.p) {
                            result[word.w].positive += word.c;
                        }
                        else {
                            result[word.w].negative += word.c;
                        }
                    });
                }
                else {
                    Object.keys(value).forEach(function (key) {
                        if (result[key]) {
                            result[key].positive += value[key].positive;
                            result[key].negative += value[key].negative;
                        }
                        else {
                            result[key] = value[key];
                        }
                    });
                }
            });
            return result;
        }''')

        finalize = Code('''function (key, value) {
            var result = [];
            Object.keys(value).forEach(function (key) {
                if (value[key].positive > 0) {
                    result.push({w: key, p: true, c: value[key].positive});
                }
                if (value[key].negative > 0) {
                    result.push({w: key, p: false, c: value[key].negative});
                }
            });
            return result;
        }''')

        if self.latest_review_date and self.latest_review_date > datetime.now() - timedelta(days=31):
            self.db[self.retailer].map_reduce(
                Code('''function () {
                    if (this.words) {
                        var product_id = this.product_id,
                            date = this.date,
                            month = date.getMonth() + 1,
                            positive_review = this.rating >= 3;
                        if (month < 10) {
                            month = '0' + month;
                        }
                        month = ISODate(date.getFullYear() + '-' + month + '-01');
                        this.words.forEach(function (word) {
                            value = {};
                            if (positive_review) {
                                value[word.w] = {positive: word.c, negative: 0};
                            }
                            else {
                                value[word.w] = {positive: 0, negative: word.c};
                            }
                            emit({
                                product_id: product_id,
                                type: 'all',
                            }, value);
                            emit({
                                product_id: product_id,
                                type: 'day',
                                date: date,
                            }, value);
                            emit({
                                product_id: product_id,
                                type: 'month',
                                date: month,
                            }, value);
                        });
                    };
                }'''),
                reduce,
                {'reduce': collection, 'nonAtomic': True},
                finalize=finalize,
                query=query,
            )
        else:
            self.db[self.retailer].map_reduce(
                Code('''function () {
                    if (this.words) {
                        var product_id = this.product_id,
                            date = this.date,
                            positive_review = this.rating >= 3;
                        this.words.forEach(function (word) {
                            value = {};
                            if (positive_review) {
                                value[word.w] = {positive: word.c, negative: 0};
                            }
                            else {
                                value[word.w] = {positive: 0, negative: word.c};
                            }
                            emit({
                                product_id: product_id,
                                type: 'day',
                                date: date,
                            }, value);
                        });
                    };
                }'''),
                reduce,
                {'reduce': collection, 'nonAtomic': True},
                finalize=finalize,
                query=query,
            )

            query = {'_id.product_id': product_id, '_id.type': 'day'}
            if self.latest_review_date:
                query['_id.date'] = {'$gte': datetime(self.latest_review_date.year, self.latest_review_date.month, 1)}
            self.db[collection].map_reduce(
                Code('''function () {
                    if (this.value) {
                        var product_id = this._id.product_id,
                            date = this._id.date,
                            month = date.getMonth() + 1;
                        if (month < 10) {
                            month = '0' + month;
                        }
                        month = ISODate(date.getFullYear() + '-' + month + '-01');
                        this.value.forEach(function (word) {
                            value = {};
                            if (word.p) {
                                value[word.w] = {positive: word.c, negative: 0};
                            }
                            else {
                                value[word.w] = {positive: 0, negative: word.c};
                            }
                            emit({
                                product_id: product_id,
                                type: 'month',
                                date: month,
                            }, value);
                        });
                    };
                }'''),
                reduce,
                {'merge': collection, 'nonAtomic': True},
                finalize=finalize,
                query=query,
            )
            self.db[collection].map_reduce(
                Code('''function () {
                    if (this.value) {
                        var product_id = this._id.product_id;
                        this.value.forEach(function (word) {
                            value = {};
                            if (word.p) {
                                value[word.w] = {positive: word.c, negative: 0};
                            }
                            else {
                                value[word.w] = {positive: 0, negative: word.c};
                            }
                            emit({
                                product_id: product_id,
                                type: 'all',
                            }, value);
                        });
                    };
                }'''),
                reduce,
                {'merge': collection, 'nonAtomic': True},
                finalize=finalize,
                query={'_id.product_id': product_id, '_id.type': 'month'},
            )

    def _update_words_count(self, review):
        words = defaultdict(int)
        for text in (review.get('title'), review.get('text')):
            if not text:
                continue
            for word in re.split('[\W\d_]+', text, flags=re.U):
                word = word.lower()
                if len(word) < 3 or word in self.stop_words:
                    continue
                words[word] += 1
        review['words'] = [{'w': word, 'c': count} for word, count in words.iteritems()]

    def _save_review(self, review):
        self._update_words_count(review)

        self.logger.debug(review)

        result = self.db[self.retailer].insert_one(review)

        if not self.first_review_id:
            self.first_review_id = result.inserted_id

        self.reviews_counter += 1
        self.reviews_by_rating_counter[str(review['rating'])] += 1
        if self.reviews_counter % 100 == 0:
            self.logger.info('Scraped {} reviews'.format(self.reviews_counter))

    def _get_first_date(self, product_id):
        first_review = self.db[self.retailer].find_one({'product_id': product_id}, sort=[('date', ASCENDING)])

        if first_review:
            return first_review['date']

    def _get_latest_date(self, product_id):
        latest_review = self.db[self.retailer].find_one({'product_id': product_id}, sort=[('date', DESCENDING)])

        if latest_review:
            self.latest_review_date = latest_review['date']
            return self.latest_review_date
        else:
            self.latest_review_date = False

    def _check_comments_update(self, product_id, has_review):
        comments_update = self.db.comments_update.find_one({'retailer': self.retailer, 'product_id': product_id})

        if not comments_update and has_review:
            # spread updates for existed reviews over a week
            comments_update = {
                'retailer': self.retailer,
                'product_id': product_id,
                'date': datetime.now() - timedelta(days=random.randint(1, 7))
            }
            self.db[self.retailer].update_many(
                {'product_id': product_id, 'comments_count': None},
                {'$set': {'comments_count': 0, 'comments': []}})
            self.db.comments_update.insert_one(comments_update)

        if comments_update and 'date' in comments_update:
            self.logger.info('Last comments update: {}'.format(comments_update['date']))
            age = datetime.now() - comments_update['date'] + timedelta(hours=12)
            return age.days >= 7
        else:
            return True

    def _set_comments_update(self, product_id):
        self.db.comments_update.update_one(
            {'retailer': self.retailer, 'product_id': product_id},
            {'$set': {'date': datetime.now()}})

    def _check_duplicate(self, review):
        return self.db[self.retailer].find_one({
            'product_id': review['product_id'],
            'date': review['date'],
            'author_name': review['author_name'],
            'title': review['title']
        })

    def _clear_reviews(self, product_id, latest_date):
        search_flter = {
            'product_id': product_id
        }

        if latest_date:
            search_flter['date'] = {'$gt': latest_date}

        self.db[self.retailer].delete_many(search_flter)

    def crawl(self, task):
        raise NotImplementedError

    def _send_request(self, *args, **kwargs):
        first_try_without_proxy = kwargs.pop('first_try_without_proxy', False)
        proxies = kwargs.pop('proxies', None)
        rotate_proxies = proxies is None
        timeout = kwargs.pop('timeout', 60)
        if not isinstance(timeout, tuple):
            timeout = (3, timeout)
        response = None

        for i in range(self.max_retries):
            try:
                if rotate_proxies and (not first_try_without_proxy or i):
                    proxies = self._get_proxies()

                if proxies:
                    self.logger.info('Using proxies: {}'.format(proxies))
                    kwargs.setdefault('headers', {})['Connection'] = 'close'

                response = requests.request(*args, proxies=proxies, timeout=timeout, **kwargs)

                if response.status_code == requests.codes.ok:
                    return response

                self.logger.warn('Response error {}, retry request: {}'.format(response.status_code, i + 1))
            except:
                self.logger.warn(traceback.format_exc())

            time.sleep(i + 1)
        else:
            message = 'Failed after retries'

            if response is not None:
                if response.status_code == requests.codes.not_found:
                    message = 'Product not found'

            raise ReviewSpiderError(message)

    def _get_proxies(self):
        if self.proxies:
            proxies = reduce(lambda x, (p, weight): x + [p] * weight, self.proxies.iteritems(), [])

            proxy = random.choice(proxies)

            return {
                'http': proxy,
                'https': proxy
            }
