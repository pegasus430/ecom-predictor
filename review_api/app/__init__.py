import hmac
import traceback
import json
import socket
import csv
from datetime import datetime
from datetime import timedelta
from heapq import nlargest
import uuid

import re
import os
from operator import itemgetter

import requests
from flask import abort
from flask import Flask, render_template, request, flash, url_for, redirect, send_file, Response, jsonify
from flask_restful import Resource, Api, reqparse, inputs
from flask_login import login_required
from bson import ObjectId
from bson.json_util import dumps, JSONOptions, JSONMode
from werkzeug.exceptions import HTTPException
from pymongo import DESCENDING, ASCENDING

from pagination import Paginate
from models import Alert, Task, Review
from database import init
from spiders import load_spiders

STATE_RECEIVED = 'received'
STATE_PROCESSING = 'processing'
STATE_READY = 'ready'
STATE_ERROR = 'error'
STATE_SUCCESS = 'success'

app = Flask(__name__)
app.config.from_object('config')

db = init(app)

import auth

spiders = load_spiders(app.config['SPIDERS_PACKAGE'])


def check_queue(task):
    queue_task = db.tasks.find_one(task)

    if queue_task:
        app.logger.warn('There is task in queue: {}'.format(task))
        return queue_task


@app.template_filter('dump')
def dump(o):
    return dumps(o, json_options=JSONOptions(json_mode=JSONMode.RELAXED))


@app.template_filter('pluralize')
def pluralize(number, singular='', plural='s'):
    if number == 1:
        return singular
    else:
        return plural


@app.template_global('get_state')
def get_state(task):
    if task['started_at']:
        if task['ended_at']:
            if task['message']:
                return STATE_ERROR
            else:
                return STATE_READY
        else:
            return STATE_PROCESSING
    else:
        return STATE_RECEIVED


@app.context_processor
def retailers():
    return dict(retailers=sorted(spiders.keys()))


@app.route('/', defaults={'task_id': None}, methods=['GET', 'POST'])
@app.route('/tasks/<task_id>')
@login_required
def index(task_id):
    page_reload = False

    try:
        if task_id:
            if len(task_id) != 24:
                return jsonify({
                    'status': STATE_ERROR,
                    'message': 'Invalid task id. Length must be equal 24'
                }), 400

            flash('Click "Reviews" to check results after finish')
            tasks = db.tasks.find({'_id': ObjectId(task_id)})
            page_reload = True
        else:
            tasks = db.tasks.find(get_search_filter()).sort('_id', DESCENDING)

        tasks = Paginate(tasks, per_page=app.config['PAGINATION'])
    except HTTPException:
        raise
    except:
        app.logger.error(traceback.format_exc())
        return jsonify({
            'status': STATE_ERROR,
            'message': 'Request could not be processed'
        }), 500
    else:
        return render_template('index.html', title='Tasks', tasks=tasks, reload=page_reload)


@app.route('/tasks/daily', defaults={'retailer': None, 'product_id': None}, methods=['GET', 'POST'])
@app.route('/tasks/daily/<retailer>/<product_id>')
@login_required
def daily_tasks(retailer, product_id):
    try:
        if retailer and product_id:
            tasks = db.daily_tasks.find({'retailer': retailer, 'product_id': product_id})
        else:
            tasks = db.daily_tasks.find(get_search_filter()).sort('last_run_at', ASCENDING)

        tasks = Paginate(tasks, per_page=app.config['PAGINATION'])
    except:
        app.logger.error(traceback.format_exc())
        return jsonify({
            'status': STATE_ERROR,
            'message': 'Request could not be processed'
        }), 500
    else:
        return render_template('daily_tasks.html', title='Recurring tasks', tasks=tasks)


@app.route('/tasks/daily/disable', methods=['GET', 'POST'])
@login_required
def disable_daily_task():
    try:
        search_filter = get_search_filter()

        if search_filter:
            db.daily_tasks.delete_many(search_filter)
        else:
            retailer = request.args.get('retailer')
            product_id = request.args.get('product_id')
            server = request.args.get('server')

            if retailer and product_id:
                db.daily_tasks.delete_one({
                    'retailer': retailer,
                    'product_id': product_id,
                    'server': server
                })

        return redirect(url_for('daily_tasks'))
    except:
        app.logger.error(traceback.format_exc())
        return jsonify({
            'status': STATE_ERROR,
            'message': 'Request could not be processed'
        }), 500


@app.route('/stats')
@login_required
def show_stats():
    try:
        stats = {}

        for retailer in spiders.keys():
            stats[retailer] = {
                'products': len(db[retailer].distinct('product_id')),
                'reviews': db[retailer].count(),
                'queue': db.tasks.find({'retailer': retailer, 'started_at': None}).count()
            }
    except:
        app.logger.error(traceback.format_exc())
        return jsonify({
            'status': STATE_ERROR,
            'message': 'Request could not be processed'
        }), 500
    else:
        return render_template('stats.html', title='Stats', stats=stats)


@app.route('/<retailer>/<product_id>/reviews')
@login_required
def show_reviews(retailer, product_id):
    reviews_filter = {'product_id': product_id}
    filter = request.args.get('filter')
    if filter:
        try:
            custom_filter = json.loads(filter)

            for field in custom_filter:
                if isinstance(custom_filter[field], basestring):
                    custom_filter[field] = re.compile(re.escape(custom_filter[field]), re.I)
        except:
            return {
                       'status': STATE_ERROR,
                       'message': 'Invalid filter. It must be url encoded JSON object'
                   }, 400
        else:
            app.logger.info('Custom filter: {}'.format(custom_filter))
            reviews_filter.update(custom_filter)

    try:
        reviews = db[retailer].find(reviews_filter).sort('date', DESCENDING)

        reviews = Paginate(reviews, per_page=app.config['PAGINATION'])
    except:
        app.logger.error(traceback.format_exc())
        return jsonify({
            'status': STATE_ERROR,
            'message': 'Request could not be processed'
        }), 500
    else:
        title = 'Reviews'

        if reviews.items.count():
            product_name = reviews.items[0].get('product_name')
            if product_name:
                title += ' - ' + product_name

        return render_template('reviews.html', title=title, retailer=retailer,
                               product_id=product_id, filter=filter, reviews=reviews)


@app.route('/<retailer>/<product_id>/reviews/delete')
@app.route('/<retailer>/reviews/delete', defaults={'product_id': None}, methods=['POST'])
@login_required
def delete_reviews(retailer, product_id):
    try:
        search_filter = get_search_filter()
        words_filter = {'_id.' + k: v for k, v in search_filter.items()}

        if search_filter:
            db[retailer].delete_many(search_filter)
        else:
            db[retailer].delete_many({
                'product_id': product_id
            })
            words_filter['_id.product_id'] = product_id
        db['words_%s' % retailer].delete_many(words_filter)

        return redirect(url_for('show_products', retailer=retailer))
    except:
        app.logger.error(traceback.format_exc())
        return jsonify({
            'status': STATE_ERROR,
            'message': 'Request could not be processed'
        }), 500


@app.route('/<retailer>/<product_id>/reviews/export')
@app.route('/<retailer>/reviews/export', defaults={'product_id': None}, methods=['POST'])
@login_required
@app.route('/<retailer>/<product_id>/reviews/export/<signature>', endpoint='download_reviews')
@app.route('/<retailer>/groups/<group_id>/reviews/export/<signature>', defaults={'product_id': None},
           endpoint='download_group_reviews')
def export_reviews(retailer, product_id, group_id=None, signature=None):
    export_format = request.args.get('format', 'jl')

    if export_format not in ('jl', 'csv'):
        return jsonify({
            'status': STATE_ERROR,
            'message': 'Unknown export format. Allowed values: jl, csv'
        }), 400

    if signature and signature.encode('utf-8').lower() != sign_export(retailer, product_id or group_id):
        abort(403)

    try:
        search_filter = get_search_filter()

        if search_filter:
            reviews = db[retailer].find(search_filter, {'_id': 0}).sort('date', DESCENDING)
        elif group_id:
            reviews = db.tasks.aggregate([
                {
                    '$match': {
                        'group_id': group_id
                    }
                },
                {
                    '$group': {
                        '_id': '$product_id'
                    }
                },
                {
                    '$lookup': {
                        'from': retailer,
                        'localField': '_id',
                        'foreignField': 'product_id',
                        'as': 'reviews',
                    }
                },
                {
                    '$unwind': '$reviews'
                },
                {
                    '$replaceRoot': {
                        'newRoot': '$reviews'
                    }
                }
            ])
        else:
            reviews = db[retailer].find({'product_id': product_id}, {'_id': 0}).sort('date', DESCENDING)

        if export_format == 'jl':
            return Response(
                ReviewAPI.jl_generator(reviews),
                mimetype='text/plain',
                headers={'Content-Disposition': 'attachment;filename="{}.jl"'.format(
                    product_id or group_id or retailer)}
            )
        elif export_format == 'csv':
            fields = spiders[retailer].review_class.fields

            if 'comments_count' not in fields:
                fields.append('comments_count')

            return Response(
                ReviewAPI.csv_generator(reviews, fields),
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment;filename="{}.csv"'.format(
                    product_id or group_id or retailer)}
            )
    except:
        app.logger.error(traceback.format_exc())
        return jsonify({
            'status': STATE_ERROR,
            'message': 'Request could not be processed'
        }), 500


@app.route('/tasks/<task_id>/log')
@login_required
def download_log(task_id):
    if len(task_id) != 24:
        return jsonify({
            'status': STATE_ERROR,
            'message': 'Invalid task id. Length must be equal 24'
        }), 400

    try:
        resource_path = os.path.join(app.config['RESOURCES_DIR'], task_id, 'task.log')

        if not os.path.exists(resource_path):
            return jsonify({
                'status': STATE_ERROR,
                'message': 'There is not log file'
            }), 404

        return send_file(resource_path, as_attachment=True, attachment_filename='{}.log'.format(task_id))
    except HTTPException:
        raise
    except:
        app.logger.error(traceback.format_exc())
        return jsonify({
            'status': STATE_ERROR,
            'message': 'Request could not be processed'
        }), 500


@app.route('/tasks/<task_id>/rerun', methods=['POST'])
@app.route('/tasks/rerun', methods=['POST'])
@login_required
def rerun_task(task_id=None):
    if task_id:
        status_code = None
        try:
            response = requests.post(
                url_for('task_rerun', task_id=task_id, _external=True),
                headers={
                    app.config['API_KEY_HEADER']:  auth.get_api_key()
                })
            status_code = response.status_code
            data = response.json()

            if status_code == requests.codes.ok and data.get('status') == STATE_RECEIVED:
                return redirect(url_for('index', task_id=data['task_id']))

            if 'message' in data:
                flash(data['message'])
        except:
            app.logger.error('Re-run task error: {}'.format(traceback.format_exc()))
            flash('Could not re-run the task. Check logs')

        if status_code == 404:
            return redirect(url_for('index'))
    else:
        try:
            period = int(request.form.get('period'))
        except:
            flash('Invalid period')
        else:
            tasks = db.tasks.find({'message': {'$ne': None},
                                   'ended_at': {'$gte': datetime.now() - timedelta(minutes=period)}},
                                  projection={'_id': False, 'started_at': False, 'ended_at': False, 'message': False})
            created = set()
            for task in tasks:
                key = (task['retailer'], task['product_id'])
                if key not in created:
                    new_task = Task(**task)

                    queue_task = check_queue(new_task)
                    if not queue_task:
                        db.tasks.insert_one(new_task)
                        created.add(key)
            if created:
                flash('Re-ran {} tasks'.format(len(created)))
            else:
                flash('No tasks to re-run')

    return redirect(url_for('index', task_id=task_id))


@app.route('/tasks/create', methods=['GET', 'POST'])
@login_required
def create_task():
    if request.method == 'GET':
        return render_template('create_task.html', title='Create task')

    group_id = request.form.get('group_id')
    if group_id:
        if db.tasks.find_one({'group_id': group_id}):
            flash('Group id already in use')
            return render_template('create_task.html', title='Create task')
    else:
        group_id = uuid.uuid4().get_hex()

    daily_frequency = request.form.get('daily_frequency')
    if daily_frequency:
        try:
            daily_frequency = int(daily_frequency)
        except:
            flash('Daily frequency should be a number of hours')
            return render_template('create_task.html', title='Create task')
    else:
        daily_frequency = None

    notify_emails = request.form.get('notify_email')
    notify_emails = filter(None, map(lambda x: x.strip(), re.split(r'[, ]', notify_emails)))

    product_ids = request.form.get('product_id')
    product_ids = filter(None, map(lambda x: re.sub(r'\W', '', x.strip()), re.split(r'[\n, ]', product_ids)))

    product_urls = request.form.get('product_url')
    product_urls = filter(None, map(lambda x: x.strip(), re.split(r'[\n, ]', product_urls)))

    if product_ids and product_urls and len(product_ids) != len(product_urls):
        flash('Number of product urls is not equal number of product ids')
        return render_template('create_task.html', title='Create task')

    retailer = request.form.get('retailer')
    spider_class = spiders.get(retailer)

    if not spider_class:
        flash('Not supporting retailer: {}'.format(retailer))
        return render_template('create_task.html', title='Create task')

    get_product_id_from_url = getattr(spider_class, 'get_product_id_from_url', None)

    for product_id, product_url in map(None, product_ids, product_urls):
        if not product_id and product_url:
            if not callable(get_product_id_from_url):
                flash('Add product id for each url')
                return render_template('create_task.html', title='Create task')

            product_id = get_product_id_from_url(product_url)

        if not product_id:
            flash('Missing product id')
            return render_template('create_task.html', title='Create task')

        new_task = {
            'retailer': retailer,
            'product_id': product_id,
            'product_url': product_url,
            'group_id': group_id,
            'from_date': request.form.get('from_date'),
            'daily_frequency': daily_frequency,
            'notify_email': notify_emails
        }

        try:
            response = requests.post(
                url_for('tasks', _external=True),
                json=new_task,
                headers={
                    app.config['API_KEY_HEADER']:  auth.get_api_key()
                })

            if len(product_ids) == 1:
                return redirect(url_for('index', task_id=response.json().get('task_id')))
        except:
            app.logger.error('Create task error: {}'.format(traceback.format_exc()))
            flash('Could not create new task. Check logs')

            return render_template('create_task.html', title='Create task')

    return redirect(url_for('index'))


@app.route('/products/<retailer>', methods=['GET', 'POST'])
@login_required
def show_products(retailer):
    try:
        search_filter = get_search_filter()

        products = sorted(db[retailer].distinct('product_id', search_filter))

        products = Paginate(products, per_page=app.config['PAGINATION'], count=len(products))

        products.items = db[retailer].aggregate([
            {
                '$match': {
                    'product_id': {
                        '$in': products.items
                    }
                }
            },
            {
                '$sort': {
                    'date': DESCENDING
                }
            },
            {
                '$group': {
                    '_id': '$product_id',
                    'last_review_date': {
                        '$first': '$date'
                    }
                }
            },
            {
                '$sort': {
                    '_id': ASCENDING
                }
            }
        ])
    except:
        app.logger.error(traceback.format_exc())
        return jsonify({
            'status': STATE_ERROR,
            'message': 'Request could not be processed'
        }), 500
    else:
        return render_template('products.html', title='{} products'.format(retailer.capitalize()),
                               retailer=retailer, products=products)


def sign_export(retailer, export_id):
    return hmac.new(app.config['CSRF_SESSION_KEY'], '{}/{}'.format(retailer, export_id)).hexdigest().lower()


def get_server():
    try:
        server = socket.gethostbyaddr(request.remote_addr)[0]
    except:
        server = 'unknown'

    return server


def get_search_filter():
    search_filter = {}

    retailer = request.form.get('retailer')
    if retailer:
        search_filter['retailer'] = retailer

    product_id = request.form.get('product_id')
    if product_id:
        products = filter(None, map(lambda x: re.sub(r'\W', '', x.strip()), re.split(r'[\n, ]', product_id)))

        search_filter['product_id'] = {'$in': map(lambda x: re.compile(x, re.I), products)}

    group_id = request.form.get('group_id')
    if group_id:
        groups = filter(None, map(lambda x: re.sub(r'\W', '', x.strip()), re.split(r'[\n, ]', group_id)))

        search_filter['group_id'] = {'$in': map(lambda x: re.compile(x, re.I), groups)}

    return search_filter


class AlertListAPI(Resource):

    decorators = [login_required]

    def post(self):
        if not request.json:
            return {
                'status': STATE_ERROR,
                'message': 'Request data is not JSON'
            }, 400

        try:
            alert = Alert(**request.json)

            alert_id = db.alerts.insert_one(alert).inserted_id

            return {
                'status': STATE_SUCCESS,
                'alert_id': str(alert_id)
            }
        except:
            app.logger.error(traceback.format_exc())
            return {
                'status': STATE_ERROR,
                'message': 'Request could not be processed'
            }, 500


class AlertAPI(Resource):

    decorators = [login_required]

    def put(self, alert_id):
        if len(alert_id) != 24:
            return {
                'status': STATE_ERROR,
                'message': 'Invalid alert id. Length must be equal 24'
            }, 400

        if not request.json:
            return {
                'status': STATE_ERROR,
                'message': 'Request data is not JSON'
            }, 400

        result = db.alerts.update_one({'_id': ObjectId(alert_id)},
                                      {'$set': {'notify_email': request.json.get('notify_email')}})

        if result.matched_count:
            return {
                'status': STATE_SUCCESS
            }
        else:
            app.logger.warn('{}: alert not found'.format(alert_id))
            return {
                'status': STATE_ERROR,
                'message': "Alert with id '{}' not found".format(alert_id),
                'alert_id': alert_id
            }, 404

    def delete(self, alert_id):
        if len(alert_id) != 24:
            return {
                'status': STATE_ERROR,
                'message': 'Invalid alert id. Length must be equal 24'
            }, 400

        result = db.alerts.delete_one({'_id': ObjectId(alert_id)})

        if result.deleted_count:
            return {
                'status': STATE_SUCCESS
            }
        else:
            app.logger.warn('{}: alert not found'.format(alert_id))
            return {
                'status': STATE_ERROR,
                'message': "Alert with id '{}' not found".format(alert_id),
                'alert_id': alert_id
            }, 404


class TaskListAPI(Resource):

    decorators = [login_required]

    def post(self):
        if not request.json:
            return {
                'status': STATE_ERROR,
                'message': 'Request data is not JSON'
            }, 400

        try:
            task = Task(server=get_server(), **request.json)

            queue_task = check_queue(task)
            if queue_task:
                task_id = queue_task['_id']
            else:
                task_id = db.tasks.insert_one(task).inserted_id

            return {
                'status': STATE_RECEIVED,
                'task_id': str(task_id)
            }
        except:
            app.logger.error(traceback.format_exc())
            return {
                'status': STATE_ERROR,
                'message': 'Request could not be processed'
            }, 500


class TaskAPI(Resource):

    decorators = [login_required]

    def get(self, task_id):
        if len(task_id) != 24:
            return {
                'status': STATE_ERROR,
                'message': 'Invalid task id. Length must be equal 24'
            }, 400

        app.logger.info('{}: checking status of task'.format(task_id))

        task = db.tasks.find_one(ObjectId(task_id))

        if not task:
            app.logger.warn('{}: task not found'.format(task_id))
            return {
                'status': STATE_ERROR,
                'message': "Task with id '{}' not found".format(task_id),
                'task_id': task_id
            }, 404

        try:
            response = {
                'status': get_state(task),
                'task_id': str(task['_id'])
            }

            log_message = "{}: status '{}'".format(task['_id'], get_state(task))

            if task.get('message'):
                response['message'] = task['message']
                log_message += ", message '{}'".format(task['message'])

            app.logger.info(log_message)

            return response
        except:
            app.logger.error(traceback.format_exc())
            return {
                'status': STATE_ERROR,
                'message': 'Request could not be processed'
            }, 500


class TaskRerunAPI(Resource):

    decorators = [login_required]

    def post(self, task_id):
        if len(task_id) != 24:
            return {
                'status': STATE_ERROR,
                'message': 'Invalid task id. Length must be equal 24'
            }, 400

        app.logger.info('{}: re-run task'.format(task_id))

        task = db.tasks.find_one(ObjectId(task_id),
                                 projection={'_id': False, 'started_at': False, 'ended_at': False})

        if not task:
            app.logger.warn('{}: task not found'.format(task_id))
            return {
                'status': STATE_ERROR,
                'message': "Task with id '{}' not found".format(task_id),
                'task_id': task_id
            }, 404

        if not task['message']:
            app.logger.warn('{}: task is not failed'.format(task_id))
            return {
                'status': STATE_ERROR,
                'message': "Task with id '{}' is not failed".format(task_id),
                'task_id': task_id
            }, 400

        try:
            task['message'] = None
            new_task = Task(**task)

            queue_task = check_queue(new_task)
            if queue_task:
                new_task_id = queue_task['_id']
            else:
                new_task_id = db.tasks.insert_one(new_task).inserted_id

            return {
                'status': STATE_RECEIVED,
                'task_id': str(new_task_id)
            }
        except:
            app.logger.error(traceback.format_exc())
            return {
                'status': STATE_ERROR,
                'message': 'Request could not be processed'
            }, 500


class WordsMixin(object):
    def _get_precounted_words(self, retailer, product_id, limit):
        words = db['words_%s' % retailer].find_one({'_id.product_id': product_id, '_id.type': 'all'}) or {}
        return [{
            'count': int(word['c']),
            'positive_review': word['p'],
            'word': word['w']
        } for word in nlargest(limit, words.get('value', []), key=itemgetter('c'))]


class ReviewAPI(Resource, WordsMixin):

    decorators = [login_required]

    def get(self, retailer, product_id):
        parser = reqparse.RequestParser()
        parser.add_argument('avg_rating_date', help='Date format YYYY-MM-DD')
        parser.add_argument('not_daily', help='Disable reviews recrawl')
        parser.add_argument('frequency', type=int, help='Set recrawl frequency in hours')
        parser.add_argument('page', type=int, help='Paginate reviews')
        parser.add_argument('per_page', type=int, default=app.config['PAGINATION'],
                            help='Limit number of reviews per page')
        parser.add_argument('total', type=inputs.boolean, default=False, help='Show total number of reviews')
        parser.add_argument('variants', type=inputs.boolean, default=False, help='Show variants for reviews')
        parser.add_argument('words', type=int, help='Show n top words from reviews')
        parser.add_argument('filter', help='Reviews filter')
        parser.add_argument('date_from', help='Reviews start date, format YYYY-MM-DD')
        parser.add_argument('date_to', help='Reviews end date, format YYYY-MM-DD')
        parser.add_argument('sort', help='Reviews sort')
        args = parser.parse_args()

        if args.avg_rating_date:
            return self._get_avg_rating(retailer, product_id, args.avg_rating_date)

        if args.not_daily:
            return self._not_daily(retailer, product_id, get_server())

        if args.frequency:
            return self._frequency(retailer, product_id, get_server(), args.frequency)

        reviews_filter = {'product_id': product_id}
        if args.filter:
            try:
                custom_filter = json.loads(args.filter)

                for field in custom_filter:
                    if isinstance(custom_filter[field], basestring):
                        custom_filter[field] = re.compile(re.escape(custom_filter[field]), re.I)
            except:
                return {
                    'status': STATE_ERROR,
                    'message': 'Invalid filter. It must be url encoded JSON object'
                }, 400
            else:
                app.logger.info('Custom filter: {}'.format(custom_filter))
                reviews_filter.update(custom_filter)

        reviews_date_filter = {}
        if args.date_from:
            try:
                reviews_date_filter['$gte'] = datetime.strptime(args.date_from, '%Y-%m-%d')
            except ValueError:
                return {
                    'status': STATE_ERROR,
                    'message': {'date_from': 'Date format YYYY-MM-DD'}
                }, 400
        if args.date_to:
            try:
                reviews_date_filter['$lte'] = datetime.strptime(args.date_to, '%Y-%m-%d')
            except ValueError:
                return {
                    'status': STATE_ERROR,
                    'message': {'date_to': 'Date format YYYY-MM-DD'}
                }, 400
        if reviews_date_filter:
            reviews_filter['date'] = reviews_date_filter

        sort = [('date', DESCENDING)]
        if args.sort:
            try:
                custom_sort = json.loads(args.sort)
            except:
                return {
                    'status': STATE_ERROR,
                    'message': 'Invalid sort. It must be url encoded JSON object'
                }, 400
            else:
                app.logger.info('Custom sort: {}'.format(custom_sort))
                sort = custom_sort

        reviews = db[retailer].find(reviews_filter, {'_id': 0, 'words': 0}, sort=sort)

        meta_response = {}

        if args.variants:
            meta_response.update({
                'status': STATE_SUCCESS,
                'variants': self._get_variants(retailer, reviews_filter)
            })

        if args.words:
            if not args.filter and not reviews_date_filter:
                words = self._get_precounted_words(retailer, product_id, args.words)
            else:
                words = self._get_words(retailer, reviews_filter, args.words)
            meta_response.update({
                'status': STATE_SUCCESS,
                'words': words
            })

        if args.total:
            meta_response.update({
                'status': STATE_SUCCESS,
                'total': reviews.count()
            })

        if meta_response:
            return meta_response

        if args.page:
            reviews = reviews[(args.page - 1) * args.per_page:args.page * args.per_page]

        return Response(self.jl_generator(reviews))

    def _get_avg_rating(self, retailer, product_id, avg_rating_date):
        avg_rating = db[retailer].aggregate([
            {
                '$match': {
                    'product_id': product_id,
                    'date': {
                        '$lt': datetime.strptime(avg_rating_date, '%Y-%m-%d')
                    }
                }
            },
            {
                '$group': {
                    '_id': '$product_id',
                    'avg_rating': {
                        '$avg': '$rating'
                    }
                }
            },
            {
                '$project': {
                    '_id': 0
                }
            }
        ])

        result = next(avg_rating, None)
        if result and result.get('avg_rating'):
            return {
                'status': STATE_SUCCESS,
                'avg_rating': result
            }
        else:
            return {
                'status': STATE_ERROR,
                'message': 'There are not reviews'
            }, 404

    def _get_variants(self, retailer, reviews_filter):
        variants = db[retailer].aggregate([
            {'$match': reviews_filter},
            {'$unwind': '$variant'},
            {
                '$group': {
                    '_id': '$variant.name',
                    'values': {
                        '$addToSet': '$variant.value'
                    }
                }
            }
        ])

        return dict((v['_id'], v['values']) for v in variants)

    def _get_words(self, retailer, reviews_filter, limit):
        words = db[retailer].aggregate([
            {'$match': reviews_filter},
            {'$unwind': '$words'},
            {
                '$group': {
                    '_id': {'word': '$words.w', 'positive_review': {'$gte': ['$rating', 3]}},
                    'count': {'$sum': '$words.c'}
                }
            },
            {
                '$project' : {
                    '_id': 0,
                    'word': '$_id.word',
                    'positive_review': '$_id.positive_review',
                    'count': '$count'
                }
            },
            {'$sort': {'count': -1}},
            {'$limit': limit}
        ])

        return list(words)

    def _not_daily(self, retailer, product_id, server):
        result = db.daily_tasks.delete_one({
            'retailer': retailer,
            'product_id': product_id,
            'server': server
        })
        if result.deleted_count:
            return {
                'status': STATE_SUCCESS
            }
        else:
            return {
                'status': STATE_ERROR,
                'message': 'There is not daily task'
            }, 404

    def _frequency(self, retailer, product_id, server, frequency):
        if frequency <= 0:
            return {
                'status': STATE_ERROR,
                'message': 'Frequency should be positive'
            }, 400
        result = db.daily_tasks.update_one({
            'retailer': retailer,
            'product_id': product_id,
            'server': server
        }, {'$set': {'frequency': frequency}})
        if result.matched_count:
            return {
                'status': STATE_SUCCESS
            }
        else:
            return {
                'status': STATE_ERROR,
                'message': 'There is not daily task'
            }, 404

    @staticmethod
    def jl_generator(reviews):
        for review in reviews:
            review['date'] = review['date'].strftime('%Y-%m-%d %H:%M:%S')
            for comment in review.get('comments') or []:
                comment['date'] = comment['date'].strftime('%Y-%m-%d %H:%M:%S')

            yield json.dumps(review) + '\n'

    @staticmethod
    def csv_generator(reviews, fields=Review.fields):
        display_fields = {
            'product_name': 'Product Name',
            'product_url': 'URL',
            'title': 'Review Title',
            'rating': 'Star Rating',
            'author_name': 'Name of Reviewer',
            'text': 'Review Description',
            'date': 'Review Date',
            'verified': 'Verified Purchase',
            'comments_count': 'Comment Count'
        }

        output_csv = csv.writer(ReviewAPI)

        yield output_csv.writerow([display_fields.get(field, field) for field in fields])

        for review in reviews:
            row = []

            for field in fields:
                value = review.get(field)

                if isinstance(value, dict):
                    value = json.dumps(value)

                if isinstance(value, list):
                    if filter(lambda x: not isinstance(x, basestring), value):
                        value = json.dumps(value)
                    else:
                        value = ','.join(value)

                if isinstance(value, unicode):
                    value = value.encode('utf-8')

                row.append(value)

            yield output_csv.writerow(row)

    @staticmethod
    def write(value):
        return value

class WordsAPI(Resource, WordsMixin):

    decorators = [login_required]

    def get(self, retailer):
        parser = reqparse.RequestParser()
        parser.add_argument('product_ids', required=True, help='Comma separated list of product ids')
        parser.add_argument('date_from', help='Reviews start date, format YYYY-MM-DD')
        parser.add_argument('date_to', help='Reviews end date, format YYYY-MM-DD')
        parser.add_argument('limit', required=True, type=int, help='Limit the number of words')
        args = parser.parse_args()

        product_ids = filter(None, map(lambda x: re.sub(r'\W', '', x.strip()), re.split(r'[\n, ]', args.product_ids)))
        if not product_ids:
            return {
                'status': STATE_ERROR,
                'message': 'No product ids'
            }, 400

        limit = args.limit
        if limit <= 0:
            return {
                'status': STATE_ERROR,
                'message': 'The limit must be positive'
            }, 400

        reviews_filter = {'_id.product_id': {'$in': product_ids}}
        date_from = None
        first_month = None
        if args.date_from:
            try:
                date_from = datetime.strptime(args.date_from, '%Y-%m-%d')
            except ValueError:
                return {
                    'status': STATE_ERROR,
                    'message': 'date_from format is YYYY-MM-DD'
                }, 400
            else:
                if date_from.day == 1:
                    first_month = date_from
                elif date_from.month == 12:
                    first_month = date_from.replace(date_from.year + 1, 1, 1)
                else:
                    first_month = date_from.replace(date_from.year, date_from.month + 1, 1)
        date_to = None
        last_month = None
        if args.date_to:
            try:
                date_to = datetime.strptime(args.date_to, '%Y-%m-%d')
            except ValueError:
                return {
                    'status': STATE_ERROR,
                    'message': 'date_to format is YYYY-MM-DD'
                }, 400
            else:
                last_month = date_to.replace(day=1)
        reviews_date_filter = []
        if first_month and last_month and first_month < last_month:
            if date_from < first_month:
                reviews_date_filter.append({'_id.type': 'day', '_id.date': {'$gte': date_from, '$lt': first_month}})
            reviews_date_filter.append({'_id.type': 'month', '_id.date': {'$gte': first_month, '$lt': last_month}})
            if date_to > last_month:
                reviews_date_filter.append({'_id.type': 'day', '_id.date': {'$gte': last_month, '$lte': date_to}})
        elif first_month and not last_month and first_month <= datetime.now():
            if date_from < first_month:
                reviews_date_filter.append({'_id.type': 'day', '_id.date': {'$gte': date_from, '$lt': first_month}})
            reviews_date_filter.append({'_id.type': 'month', '_id.date': {'$gte': first_month}})
        elif last_month and not first_month:
            reviews_date_filter.append({'_id.type': 'month', '_id.date': {'$lt': last_month}})
            if date_to > last_month:
                reviews_date_filter.append({'_id.type': 'day', '_id.date': {'$gte': last_month, '$lte': date_to}})
        elif date_from or date_to:
            reviews_date_filter.append({'_id.type': 'day', '_id.date': {}})
            if date_from:
                reviews_date_filter[-1]['_id.date']['$gte'] = date_from
            if date_to:
                reviews_date_filter[-1]['_id.date']['$lte'] = date_to
        if reviews_date_filter:
            if len(reviews_date_filter) == 1:
                reviews_filter.update(reviews_date_filter[0])
            else:
                reviews_filter['$or'] = reviews_date_filter
        else:
            reviews_filter['_id.type'] = 'all'

        if len(product_ids) == 1 and not reviews_date_filter:
            words = self._get_precounted_words(retailer, product_ids[0], limit)
        else:
            words = [{
                'count': int(word['count']),
                'positive_review': word['positive_review'],
                'word': word['word']
            } for word in db['words_%s' % retailer].aggregate([
                {'$match': reviews_filter},
                {'$unwind': '$value'},
                {
                    '$group': {
                        '_id': {'word': '$value.w', 'positive_review': '$value.p'},
                        'count': {'$sum': '$value.c'}
                    }
                },
                {
                    '$project' : {
                        '_id': 0,
                        'word': '$_id.word',
                        'positive_review': '$_id.positive_review',
                        'count': '$count'
                    }
                },
                {'$sort': {'count': -1}},
                {'$limit': limit}
            ])]
        return {
            'status': STATE_SUCCESS,
            'words': words
        }

    def post(self, retailer):
        return self.get(retailer)


class NewReviewsCountAPI(Resource):

    decorators = [login_required]

    def get(self, retailer):
        parser = reqparse.RequestParser()
        parser.add_argument('product_ids', required=True, help='Comma separated list of product ids')
        parser.add_argument('date_from', help='Reviews start date, format YYYY-MM-DD')
        args = parser.parse_args()

        product_ids = filter(None, map(lambda x: re.sub(r'\W', '', x.strip()), re.split(r'[\n, ]', args.product_ids)))
        if not product_ids:
            return {
                'status': STATE_ERROR,
                'message': 'No product ids',
            }, 400
        reviews_filter = {'product_id': {'$in': product_ids}}

        reviews_date_filter = {}
        if args.date_from:
            try:
                reviews_date_filter['$gte'] = datetime.strptime(args.date_from, '%Y-%m-%d')
            except ValueError:
                return {
                    'status': STATE_ERROR,
                    'message': {'date_from': 'Date format YYYY-MM-DD'},
                }, 400
        if reviews_date_filter:
            reviews_filter['date'] = reviews_date_filter
            group = {
                '_id': None,
                'total': {'$sum': '$count'},
            }
            group.update({str(i): {'$sum': {'$cond': [{'$eq': ['$_id', i]}, '$count', 0]}} for i in range(1, 6)})
            new_reviews_count = db[retailer].aggregate([
                {'$match': reviews_filter},
                {'$group': {'_id': '$rating', 'count': {'$sum': 1}}},
                {'$group': group},
                {'$project': {'_id': 0}},
            ])
        else:
            reviews_filter['retailer'] = retailer
            group = {
                '_id': None,
                'total': {'$sum': '$reviews'},
            }
            group.update({str(i): {'$sum': '$reviews_by_rating.%s' % i} for i in range(1, 6)})
            new_reviews_count = db.tasks.aggregate([
                {'$match': reviews_filter},
                {'$sort': {'_id': -1}},
                {
                    '$group': {
                        '_id': '$product_id',
                        'reviews': {'$first': '$reviews'},
                        'reviews_by_rating': {'$first': '$reviews_by_rating'},
                    }
                },
                {'$group': group},
                {'$project': {'_id': 0}},
            ])
        result = next(new_reviews_count, None)
        if not result:
            result = {str(i): 0 for i in range(1, 6)}
            result['total'] = 0
        return {
            'status': STATE_SUCCESS,
            'new_reviews_count': result,
        }

    def post(self, retailer):
        return self.get(retailer)


api = Api(app)
api.add_resource(AlertListAPI, '/api/v1/alerts', endpoint='alerts')
api.add_resource(AlertAPI, '/api/v1/alerts/<alert_id>', endpoint='alert')
api.add_resource(TaskListAPI, '/api/v1/tasks', endpoint='tasks')
api.add_resource(TaskAPI, '/api/v1/tasks/<task_id>', endpoint='task')
api.add_resource(TaskRerunAPI, '/api/v1/tasks/<task_id>/rerun', endpoint='task_rerun')
api.add_resource(ReviewAPI, '/api/v1/<retailer>/<product_id>/reviews', endpoint='reviews')
api.add_resource(NewReviewsCountAPI, '/api/v1/<retailer>/new_reviews_count', endpoint='new_reviews_count')
api.add_resource(WordsAPI, '/api/v1/<retailer>/words', endpoint='words')
