import traceback
import json
from multiprocessing.util import register_after_fork
import os
import urlparse

from flask import Flask, render_template, request, send_file
from flask_restful import Resource, Api, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import login_required, current_user

app = Flask(__name__)
app.config.from_object('config')

db = SQLAlchemy(app)
register_after_fork(db, lambda db: db.engine.dispose())

import auth
from models import Submission


@app.route('/')
@login_required
def index():
    try:
        submissions = Submission.query.order_by(Submission.created_at.desc()).\
            paginate(per_page=app.config['PAGINATION'], error_out=False)
        servers = []
        for submission in submissions.items:
            try:
                request_data = json.loads(submission.request)
                server = urlparse.urlparse(request_data['server']['url']).hostname.split('.')[0].capitalize()
                servers.append(server)
            except:
                servers.append('')
    except:
        app.logger.error(traceback.format_exc())
        abort(500, message='Request could not be processed')
    else:
        return render_template('index.html', title='Submissions', submissions=submissions, servers=servers)


@app.route('/<feed_id>/request')
@login_required
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
@login_required
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
            return send_file(resource_path)

        resources = []
        files = os.listdir(resource_path)

        for filename in sorted(files):
                file_path = os.path.join(resource_path, filename)

                if os.path.isfile(file_path):
                    resources.append(filename)

        return render_template('resources.html',  title='Resources', feed_id=feed_id, resources=resources)


class SubmissionListAPI(Resource):

    decorators = [login_required]

    def __init__(self, sandbox=False,):
        self.sandbox = sandbox

        super(SubmissionListAPI, self).__init__()

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
                sandbox=self.sandbox,
                user=current_user
            )

            db.session.add(submission)
            db.session.commit()

            return {
                'status': submission.state,
                'submission_id': submission.feed_id
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
                'submission_id': submission.feed_id
            }

            log_message = "{}: status '{}'".format(submission.feed_id, submission.state)

            if submission.message:
                response['message'] = submission.message
                log_message += ", message '{}'".format(submission.message)

            if submission.results:
                response['file'] = submission.results.url
                log_message += ", file '{}'".format(submission.results.url)

            if submission.screenshots:
                response['screenshots'] = submission.screenshots.url
                log_message += ", screenshots '{}'".format(submission.screenshots.url)

            if submission.data:
                response['data'] = submission.data.data
                log_message += ", data '{}'".format(submission.data.data)

            app.logger.info(log_message)

            return response
        except:
            app.logger.error(traceback.format_exc())
            abort(500, message='Request could not be processed')


api = Api(app)
api.add_resource(SubmissionListAPI, '/api/v1/submissions', endpoint='submissions')
api.add_resource(SubmissionListAPI, '/api/v1/sandbox/submissions', endpoint='sandbox-submissions',
                 resource_class_kwargs={'sandbox': True})
api.add_resource(SubmissionAPI, '/api/v1/submissions/<feed_id>', '/api/v1/sandbox/submissions/<feed_id>')
