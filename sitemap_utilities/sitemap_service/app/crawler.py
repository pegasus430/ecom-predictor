from celery import Celery
from app import app
from models import db, SitemapRequest, SitemapResults
from datetime import timedelta, datetime
import json
from spiders import load_spiders
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
    'process_requests': {
        'task': 'app.crawler.process_requests',
        'schedule': timedelta(seconds=app.config['CELERY_TIMEDELTA_SECONDS']),
    },
})

logger = get_task_logger(__name__)
logger.setLevel(app.config['LOG_LEVEL'])


class SitemapRequestError(Exception):
    pass


@celery.task()
def process_requests():
    while True:
        if db.session.bind.name == 'sqlite':
            db.session.execute('BEGIN IMMEDIATE TRANSACTION')

        sitemap_request = SitemapRequest.query.with_for_update().filter_by(state=SitemapRequest.STATE_RECEIVED).first()

        if not sitemap_request:
            db.session.rollback()
            break

        sitemap_request.started_at = datetime.now()
        sitemap_request.state = SitemapRequest.STATE_PROCESSING
        db.session.commit()

        request_id = sitemap_request.id
        logger.info('Processing request {}'.format(request_id))

        try:
            data = json.loads(sitemap_request.data)

            missing_fields = {'request'} - set(data.keys())
            if missing_fields:
                raise SitemapRequestError('Missing data fields: {}'.format(', '.join(missing_fields)))

            request_data = data['request']

            missing_fields = {'type', 'retailer'} - set(request_data.keys())
            if missing_fields:
                raise SitemapRequestError('Missing request fields: {}'.format(', '.join(missing_fields)))

            retailer = request_data['retailer']
            spider_class = load_spiders(app.config['SPIDERS_PACKAGE']).get(retailer)

            if not spider_class:
                raise SitemapRequestError('Not supporting retailer: {}'.format(retailer))

            spider = spider_class(request_id,
                                  app.config['SITEMAP_RESOURCES_DIR'],
                                  logger=logger)

            options = request_data.get('options') or {}
            options['request_name'] = sitemap_request.name

            result = spider.perform_task(
                task_type=request_data['type'],
                options=options,
            )

            if result.get('results'):
                sitemap_request.results = SitemapResults(result.get('results'))

            if result.get('message'):
                raise SitemapRequestError(result.get('message'))
            else:
                sitemap_request.message = 'Success'
        except SitemapRequestError as e:
            logger.error('{}: {}'.format(request_id, e.message))
            sitemap_request.state = SitemapRequest.STATE_ERROR
            sitemap_request.message = e.message
        except:
            logger.error('{}: {}'.format(request_id, traceback.format_exc()))
            sitemap_request.state = SitemapRequest.STATE_ERROR
            sitemap_request.message = 'Request could not be processed'
        else:
            sitemap_request.state = SitemapRequest.STATE_READY

        sitemap_request.ended_at = datetime.now()
        db.session.commit()
