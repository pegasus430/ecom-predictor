from celery import Celery
import cloudinary
from app import app
from models import db, Submission, SubmissionResults
from datetime import timedelta, datetime
import json
from downloaders import load_downloaders
import traceback
from celery.utils.log import get_task_logger


def make_celery(app):
    celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

celery.conf.update(CELERYBEAT_SCHEDULE={
    'process_submissions': {
        'task': 'app.downloader.process_submissions',
        'schedule': timedelta(seconds=app.config['CELERY_TIMEDELTA_SECONDS']),
    },
})

cloudinary.config(
    cloud_name=app.config['CLOUDINARY_CLOUD_NAME'],
    api_key=app.config['CLOUDINARY_API_KEY'],
    api_secret=app.config['CLOUDINARY_API_SECRET']
)

logger = get_task_logger(__name__)
logger.setLevel(app.config['LOG_LEVEL'])


class ImageSubmissionError(Exception):
    pass


@celery.task()
def process_submissions():
    while True:
        if db.session.bind.name == 'sqlite':
            db.session.execute('BEGIN IMMEDIATE TRANSACTION')

        submission = Submission.query.with_for_update().filter_by(state=Submission.STATE_RECEIVED).first()

        if not submission:
            db.session.rollback()
            break

        feed_id = submission.feed_id

        submission.started_at = datetime.now()
        submission.state = Submission.STATE_PROCESSING
        db.session.commit()

        try:
            data = json.loads(submission.request)

            missing_fields = {'submission'} - set(data.keys())
            if missing_fields:
                raise ImageSubmissionError('Missing data fields: {}'.format(', '.join(missing_fields)))

            submission_data = data['submission']

            missing_fields = {'type', 'retailer'} - set(submission_data.keys())
            if missing_fields:
                raise ImageSubmissionError('Missing submission fields: {}'.format(', '.join(missing_fields)))

            retailer = submission_data['retailer']
            downloader_class = load_downloaders(app.config['DOWNLOADERS_PACKAGE']).get(retailer)

            if not downloader_class:
                raise ImageSubmissionError('Not supporting retailer: {}'.format(retailer))

            downloader = downloader_class(feed_id,
                                          app.config['SUBMISSION_RESOURCES_DIR'],
                                          logger=logger)

            result = downloader.perform_task(
                task_type=submission_data['type'],
                options=submission_data.get('options', {}),
                server=data.get('server'),
                criteria=data.get('criteria'),
            )

            if result.get('results'):
                submission.results = SubmissionResults(result.get('results'))

            if result.get('message'):
                raise ImageSubmissionError(result.get('message'))
        except ImageSubmissionError as e:
            logger.error('{}: {}'.format(feed_id, e.message))
            submission.state = Submission.STATE_ERROR
            submission.message = e.message
        except:
            logger.error('{}: {}'.format(feed_id, traceback.format_exc()))
            submission.state = Submission.STATE_ERROR
            submission.message = 'Submission request could not be processed'
        else:
            submission.state = Submission.STATE_READY

        submission.ended_at = datetime.now()
        db.session.commit()
