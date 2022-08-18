import json
import traceback
from datetime import timedelta, datetime

from app import app
from celery import Celery
from celery.utils.log import get_task_logger

from models import db, Submission, SubmissionResults, SubmissionScreenshots, SubmissionData
from spiders import load_spiders


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
        'task': 'app.crawler.process_submissions',
        'schedule': timedelta(seconds=app.config['CELERY_PROCESS_TIMEDELTA_SECONDS']),
    },
    'check_submissions': {
        'task': 'app.crawler.check_submissions',
        'schedule': timedelta(seconds=app.config['CELERY_CHECK_TIMEDELTA_SECONDS']),
    },
})

logger = get_task_logger(__name__)
logger.setLevel(app.config['LOG_LEVEL'])


class SubmissionError(Exception):
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

        submission.started_at = datetime.now()
        submission.state = Submission.STATE_PROCESSING
        db.session.commit()

        feed_id = submission.feed_id
        logger.info('Processing submission {}'.format(feed_id))

        try:
            data = json.loads(submission.request)

            missing_fields = {'submission'} - set(data.keys())
            if missing_fields:
                raise SubmissionError('Missing data fields: {}'.format(', '.join(missing_fields)))

            submission_data = data['submission']

            missing_fields = {'type', 'retailer'} - set(submission_data.keys())
            if missing_fields:
                raise SubmissionError('Missing submission fields: {}'.format(', '.join(missing_fields)))

            retailer = submission_data['retailer']
            spider_class = load_spiders(app.config['SPIDERS_PACKAGE']).get(retailer)

            if not spider_class:
                raise SubmissionError('Not supporting retailer: {}'.format(retailer))

            spider = spider_class(
                feed_id,
                app.config['SUBMISSION_RESOURCES_DIR'],
                sandbox=submission.sandbox,
                logger=logger
            )

            result = spider.perform_task(
                task_type=submission_data['type'],
                options=submission_data.get('options', {}),
                server=data.get('server'),
                criteria=data.get('criteria'),
            )

            if result.get('screenshots'):
                submission.screenshots = SubmissionScreenshots(result.get('screenshots'))

            if result.get('results'):
                submission.results = SubmissionResults(result.get('results'))

            if result.get('data'):
                submission.data = SubmissionData(result.get('data'))

            if result.get('message'):
                raise SubmissionError(result.get('message'))
        except SubmissionError as e:
            logger.error('{}: {}'.format(feed_id, e.message))
            submission.state = Submission.STATE_ERROR
            submission.message = e.message
        except:
            logger.error('{}: {}'.format(feed_id, traceback.format_exc()))
            submission.state = Submission.STATE_ERROR
            submission.message = 'Submission request could not be processed'
        else:
            if getattr(spider, 'async_check_required', False):
                submission.async_check = True
                db.session.commit()
                spider.close_log_file()
                return

            submission.state = Submission.STATE_READY
        finally:
            if 'spider' in locals():
                spider.close_log_file()

        submission.ended_at = datetime.now()
        db.session.commit()


@celery.task()
def check_submissions():
    last_id = None

    while True:
        if db.session.bind.name == 'sqlite':
            db.session.execute('BEGIN IMMEDIATE TRANSACTION')

        submission_query = Submission.query.with_for_update().filter_by(
            state=Submission.STATE_PROCESSING, async_check=True)
        if last_id:
            submission_query = submission_query.filter(Submission.id > last_id)
        submission = submission_query.order_by(Submission.id.asc()).first()

        if not submission:
            db.session.rollback()
            break

        last_id = submission.id

        submission.async_check = False
        db.session.commit()

        feed_id = submission.feed_id
        logger.info('Checking submission {}'.format(feed_id))

        try:
            data = json.loads(submission.request)

            submission_data = data['submission']
            retailer = submission_data['retailer']

            spider_class = load_spiders(app.config['SPIDERS_PACKAGE'])[retailer]

            spider = spider_class(feed_id,
                                  app.config['SUBMISSION_RESOURCES_DIR'],
                                  sandbox=submission.sandbox,
                                  logger=logger)

            submission_request_data = submission.data.data

            options = submission_data.get('options', {})
            options.update(submission_request_data)

            result = spider.perform_task(
                task_type='check',
                options=options
            )

            if result.get('data'):
                submission_request_data.update(result.get('data'))
                submission.data.data = submission_request_data

            if result.get('message'):
                raise SubmissionError(result.get('message'))
        except SubmissionError as e:
            logger.error('{}: {}'.format(feed_id, e.message))
            submission.state = Submission.STATE_ERROR
            submission.message = e.message
        except:
            logger.error('{}: {}'.format(feed_id, traceback.format_exc()))
            submission.state = Submission.STATE_ERROR
            submission.message = 'Submission request could not be processed'
        else:
            if getattr(spider, 'async_check_required', False):
                if (datetime.now() - submission.started_at).total_seconds() > 60 * 60 * 24:
                    message = 'Submission process timeout after 24 hours'

                    logger.error('{}: {}'.format(feed_id, message))

                    submission.state = Submission.STATE_ERROR
                    submission.message = message
                else:
                    submission.async_check = True
                    db.session.commit()
                    continue
            else:
                submission.state = Submission.STATE_READY
        finally:
            if 'spider' in locals():
                spider.close_log_file()

        submission.ended_at = datetime.now()
        db.session.commit()
