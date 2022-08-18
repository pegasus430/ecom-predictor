import traceback
import json
from multiprocessing.util import register_after_fork
import os
import csv
import uuid
import urllib2

from flask import Flask, render_template, request, send_file, url_for, redirect, flash
from flask_restful import Resource, Api, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import login_required, current_user
from xlrd import open_workbook

app = Flask(__name__)
app.config.from_object('config')

db = SQLAlchemy(app)
register_after_fork(db, lambda db: db.engine.dispose())

import auth
from models import Submission


@app.route('/', defaults={'feed_id': None})
@app.route('/<feed_id>')
def index(feed_id):
    try:
        if feed_id:
            flash('Click "Browse" to check results and logs after finish')
            submissions = Submission.query.filter_by(feed_id=feed_id)
        else:
            submissions = Submission.query.order_by(Submission.created_at.desc())
        submissions = submissions.paginate(per_page=app.config['PAGINATION'], error_out=False)
    except:
        app.logger.error(traceback.format_exc())
        abort(500, message='Request could not be processed')
    else:
        return render_template('index.html', title='Submissions', submissions=submissions)


@app.route('/<feed_id>/request')
def submission_request(feed_id):
    try:
        submission = Submission.query.filter_by(feed_id=feed_id).first()
    except:
        app.logger.error(traceback.format_exc())
        abort(500, message='Request could not be processed')
    else:
        if not submission:
            abort(404)

        request_data = submission.request

        try:
            request_data = json.dumps(json.loads(request_data), indent=2)
        except:
            pass

        return render_template('request.html', title='Request', feed_id=feed_id, request=request_data)


@app.route('/<feed_id>/resources/', defaults={'resource': ''})
@app.route('/<feed_id>/resources/<resource>')
def submission_resources(feed_id, resource):
    try:
        submission = Submission.query.filter_by(feed_id=feed_id).first()
    except:
        app.logger.error(traceback.format_exc())
        abort(500, message='Request could not be processed')
    else:
        if not submission:
            abort(404)

        resource_path = os.path.join(app.config['SUBMISSION_RESOURCES_DIR'], feed_id, resource)

        if not os.path.exists(resource_path):
            abort(404)

        if os.path.isfile(resource_path):
            return send_file(resource_path, as_attachment=True)

        resources = []
        files = os.listdir(resource_path)

        for filename in sorted(files):
                file_path = os.path.join(resource_path, filename)

                if os.path.isfile(file_path):
                    resources.append(filename)

        return render_template('resources.html',  title='Resources', feed_id=feed_id, resources=resources)


@app.route('/test', methods=['GET', 'POST'])
def test():
    if request.method == 'GET':
        return render_template('test.html', title='Testing UI')

    caids_file = request.files.get('caids')
    if not caids_file:
        return render_template('test.html', title='Testing UI', caids_error=True)

    caids = parse_caids(caids_file)

    server = request.form.get('server')
    if not server:
        return render_template('test.html', title='Testing UI', server_error=True)

    retailer = request.form.get('retailer')
    differences_only = request.form.get('differences_only')
    image_type = request.form.get('image_type')
    image_resize = bool(request.form.get('image_resize'))

    try:
        image_min_side_dimension = int(request.form.get('image_min_side_dimension'))
    except:
        image_min_side_dimension = None

    submission_data = {
        'server': {
            'url': 'http://{}.contentanalyticsinc.com'.format(server),
            'api_key': get_mc_api_key(server)
        },
        'submission': {
            'type': 'images',
            'retailer': retailer,
            'options': {
                'differences_only': differences_only,
                'image_type': image_type,
                'image_resize': image_resize,
                'image_min_side_dimension': image_min_side_dimension
            }
        },
        'criteria': {
            'filter': {
                'products': caids
            }
        }
    }

    feed_id = uuid.uuid4().get_hex()

    submission_request = urllib2.Request(
        url_for('submission', _external=True),
        data=json.dumps(submission_data),
        headers={
            app.config['API_KEY_HEADER']: 'alo4yu8fj30ltb3r',
            app.config['FEED_ID_HEADER']: feed_id,
            'Content-Type': 'application/json'
        })

    urllib2.urlopen(submission_request)

    return redirect(url_for('index', feed_id=feed_id))


@app.route('/cloudinary', methods=['GET', 'POST'])
def cloudinary():
    if request.method == 'GET':
        return render_template('cloudinary.html', title='Cloudinary UI')

    urls_file = request.files.get('urls')
    if urls_file:
        urls = parse_urls(urls_file)
    else:
        urls = []

    caids_file = request.files.get('caids')
    if caids_file:
        caids = parse_caids(caids_file)
    else:
        caids = []
        if not urls_file:
            return render_template('cloudinary.html', title='Cloudinary UI', caids_error=True)

    server = request.form.get('server')
    if not server and not urls_file:
        return render_template('cloudinary.html', title='Cloudinary UI', server_error=True)

    retailer = request.form.get('retailer')
    differences_only = request.form.get('differences_only')
    image_type = request.form.get('image_type')
    image_square = bool(request.form.get('image_square'))
    image_resize = bool(request.form.get('image_resize'))

    try:
        image_min_side_dimension = int(request.form.get('image_min_side_dimension'))
    except:
        image_min_side_dimension = None

    try:
        image_max_side_dimension = int(request.form.get('image_max_side_dimension'))
    except:
        image_max_side_dimension = None

    generate_urls = bool(request.form.get('generate_urls'))

    submission_data = {
        'submission': {
            'type': 'cloudinary_urls' if generate_urls else 'cloudinary',
            'retailer': retailer,
            'options': {
                'urls': urls,
                'differences_only': differences_only,
                'image_type': image_type,
                'image_square': image_square,
                'image_resize': image_resize,
                'image_min_side_dimension': image_min_side_dimension,
                'image_max_side_dimension': image_max_side_dimension,
            },
        },
    }
    if caids and server:
        submission_data.update({
            'server': {
                'url': 'http://{}.contentanalyticsinc.com'.format(server),
                'api_key': get_mc_api_key(server),
            },
            'criteria': {
                'filter': {
                    'products': caids,
                },
            },
        })

    feed_id = uuid.uuid4().get_hex()

    submission_request = urllib2.Request(
        url_for('submission', _external=True),
        data=json.dumps(submission_data),
        headers={
            app.config['API_KEY_HEADER']: 'alo4yu8fj30ltb3r',
            app.config['FEED_ID_HEADER']: feed_id,
            'Content-Type': 'application/json',
        })

    urllib2.urlopen(submission_request)

    return redirect(url_for('index', feed_id=feed_id))


def get_mc_api_key(server):
    api_url = 'https://{}.contentanalyticsinc.com/api/token?' \
              'username=api@cai-api.com&password=jEua6jLQFRjq8Eja'.format(server)
    return json.loads(urllib2.urlopen(api_url).read())['api_key']


def parse_caids(caids_file):
    caids_csv = csv.reader(caids_file)

    # skip header
    caids_csv.next()

    return [row[0].strip() for row in caids_csv if row]


def parse_urls(urls_file):
    if urls_file.filename.endswith('.xls') or urls_file.filename.endswith('.xlsx'):
        wb = open_workbook(file_contents=urls_file.stream.read())
        ws = wb.sheet_by_index(0)
        return [ws.cell(row, 0).value.strip() for row in range(ws.nrows)]
    else:
        urls_csv = csv.reader(urls_file)
        return [row[0].strip() for row in urls_csv if row]


class SubmissionListAPI(Resource):

    decorators = [login_required]

    def post(self):
        feed_id = request.headers.get(app.config['FEED_ID_HEADER'])

        if not feed_id:
            abort(400,
                  status='error',
                  message='Request without feed_id')

        try:
            submission = Submission(
                request=request.data,
                feed_id=feed_id,
                user=current_user
            )

            db.session.add(submission)
            db.session.commit()

            return {
                'status': submission.state,
                'feed_id': submission.feed_id
            }
        except:
            app.logger.error(traceback.format_exc())
            abort(500, message='Request could not be processed')


class SubmissionAPI(Resource):

    decorators = [login_required]

    def get(self, feed_id):
        app.logger.info('{}: checking status of submission'.format(feed_id))
        submission = Submission.query.filter_by(feed_id=feed_id).first()

        if not submission:
            app.logger.warn('{}: submission not found'.format(feed_id))
            abort(404,
                  feed_id=feed_id,
                  status='error',
                  message="Submission with feed id '{}' not found".format(feed_id))

        try:
            response = {
                'status': submission.state,
                'feed_id': submission.feed_id
            }

            log_message = "{}: status '{}'".format(submission.feed_id, submission.state)

            if submission.message:
                response['message'] = submission.message
                log_message += ", message '{}'".format(submission.message)

            if submission.results:
                response['file'] = url_for('submission_resources',
                                           feed_id=feed_id,
                                           resource=submission.results.name,
                                           _external=True)
                log_message += ", file '{}'".format(submission.results.name)

            app.logger.info(log_message)

            return response
        except:
            app.logger.error(traceback.format_exc())
            abort(500, message='Request could not be processed')


api = Api(app)
api.add_resource(SubmissionListAPI, '/submission', endpoint='submission')
api.add_resource(SubmissionAPI, '/submission/<feed_id>', '/sandbox/submission/<feed_id>')
