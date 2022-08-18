import traceback
import boto
import signal
from datetime import timedelta, datetime

from app import app
from celery import Celery
from celery.utils.log import get_task_logger
from celery.schedules import crontab
from flask import url_for
from pymongo import ASCENDING, DESCENDING

from app import sign_export
from models import Task
from database import init
from spiders import load_spiders, ReviewSpiderError


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
    'crawl_reviews': {
        'task': 'app.crawler.crawl_reviews',
        'schedule': timedelta(seconds=app.config['CELERY_PROCESS_TIMEDELTA_SECONDS']),
    },
    'recrawl_reviews': {
        'task': 'app.crawler.recrawl_reviews',
        'schedule': timedelta(seconds=app.config['CELERY_PROCESS_TIMEDELTA_SECONDS']),
    },
    'send_alert': {
        'task': 'app.crawler.send_alert',
        'schedule': crontab(minute=0, hour=15),  # 7 AM PDT
    }
})

logger = get_task_logger(__name__)
logger.setLevel(app.config['LOG_LEVEL'])

spiders = load_spiders(app.config['SPIDERS_PACKAGE'])


class CrawlerError(Exception):
    pass


class CrawlerKiller:
    stop_crawler = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

    def stop(self, signum, frame):
        logger.info('Stop crawler')
        self.stop_crawler = True


@celery.task()
def crawl_reviews():
    db = init(app)

    killer = CrawlerKiller()

    while True:
        started_at = datetime.now()

        task = db.tasks.find_one_and_update(
            {'started_at': None},
            {'$set': {'started_at': started_at}},
            sort=[('_id', ASCENDING)]
        )

        if not task:
            break

        task_id = task['_id']

        logger.info('Processing task {}'.format(task_id))

        task_update = {}

        try:
            retailer = task['retailer']
            if not retailer:
                raise CrawlerError("Missing 'retailer' field")

            spider_class = spiders.get(retailer)
            if not spider_class:
                raise CrawlerError('Not supporting retailer: {}'.format(retailer))

            product_id = task['product_id']
            if not product_id:
                raise CrawlerError("Missing 'product_id' field")

            from_date = task.get('from_date')
            if from_date:
                try:
                    task['from_date'] = datetime.strptime(from_date, '%Y-%m-%d')
                except ValueError:
                    raise CrawlerError('Format for from_date param is YYYY-MM-DD')

            daily = task.get('daily')
            daily_frequency = task.get('daily_frequency')

            if daily is not None or daily_frequency is not None:
                if daily or daily_frequency:
                    logger.info('Add daily task')

                    if daily and not daily_frequency:
                        daily_frequency = 24

                    db.daily_tasks.update_one(
                        {
                            'retailer': retailer,
                            'product_id': product_id,
                            'server': task.get('server')
                        },
                        {'$set': {
                            'last_run_at': started_at,
                            'frequency': daily_frequency,
                            'product_url': task.get('product_url'),
                            'group_id': task.get('group_id'),
                            'from_date': from_date,
                            'server': task.get('server'),
                            'notify_email': task.get('notify_email')
                        }},
                        upsert=True
                    )

                    # update all other tasks for the product
                    db.daily_tasks.update_many(
                        {
                            'retailer': retailer,
                            'product_id': product_id,
                            'last_run_at': {'$ne': started_at}
                        },
                        {'$set': {'last_run_at': started_at}}
                    )
                else:
                    result = db.daily_tasks.delete_one({
                        'retailer': retailer,
                        'product_id': product_id,
                        'server': task.get('server')
                    })

                    if result.deleted_count:
                        logger.info('Daily task was removed')
                    else:
                        logger.info('Task is not daily')

            spider = spider_class(str(task_id), app.config['RESOURCES_DIR'], db, logger=logger)

            spider.crawl(task)
            spider.update_words_collection(product_id)
        except (CrawlerError, ReviewSpiderError) as e:
            logger.error('{}: {}'.format(task_id, e.message))
            task_update['message'] = e.message
        except:
            logger.error('{}: {}'.format(task_id, traceback.format_exc()))
            task_update['message'] = 'Task could not be processed'
        else:
            task_update['reviews'] = spider.reviews_counter
            task_update['reviews_by_rating'] = spider.reviews_by_rating_counter

            send_notify(db, task, spider.reviews_counter)
        finally:
            if 'spider' in locals():
                spider.close_log_file()

        task_update['ended_at'] = datetime.now()

        db.tasks.update_one({'_id': task_id}, {'$set': task_update})

        if killer.stop_crawler:
            break


@celery.task()
def recrawl_reviews():
    db = init(app)

    while True:
        last_run_at = datetime.now()

        daily_task = db.daily_tasks.find_one_and_update(
            {'$where': 'this.last_run_at < new Date(new Date().getTime() - (this.frequency || 24)*60*60*1000)'},
            {'$set': {'last_run_at': last_run_at}},
            projection={'_id': False, 'last_run_at': False},
            sort=[('last_run_at', ASCENDING)]
        )

        if not daily_task:
            break

        task = Task(**daily_task)

        queue_task = db.tasks.find_one(task)
        if queue_task:
            logger.warn('There is task in queue: {}'.format(task))
            continue

        # update all other tasks for the product
        db.daily_tasks.update_many(
            {
                'retailer': daily_task['retailer'],
                'product_id': daily_task['product_id'],
                'last_run_at': {'$ne': last_run_at}
            },
            {'$set': {'last_run_at': last_run_at}}
        )

        logger.info('Add daily task for retailer {} and product id {}'.format(
            daily_task['retailer'], daily_task['product_id']))

        db.tasks.insert_one(task)


@celery.task()
def send_alert():
    if app.config['DEV_CONFIG']:
        return

    db = init(app)

    failed_tasks = db.tasks.find({'message': {'$ne': None}, 'started_at': {'$gt': datetime.now() - timedelta(days=1)}})

    count = failed_tasks.count()

    if count:
        subject = 'Reviews Crawler Status - Failure Report ({} products impacted)'.format(count)

        body = ''

        for task in failed_tasks:
            product = db[task['retailer']].find_one({'product_id': task['product_id']}, sort=[('date', DESCENDING)])

            if product and product.get('product_name'):
                product_name = product['product_name']
            else:
                product_name = 'Unknown'

            body += u'{message} - {product_id} - {product_name} - {retailer} - {product_url}\n'.format(
                message=task['message'],
                product_id=task['product_id'],
                product_name=product_name,
                retailer=task['retailer'].capitalize(),
                product_url=task.get('product_url') or 'no url'
            )

        try:
            ses = boto.connect_ses()
            ses.send_email(source='noreply@contentanalyticsinc.com',
                           subject=subject,
                           body=body,
                           to_addresses=['support@contentanalyticsinc.com', 'c-asergeev@contentanalyticsinc.com'])
        except:
            logger.error('Can not send alert email: {}'.format(traceback.format_exc()))


def send_notify(db, task, count):
    try:
        retailer = task['retailer']
        product_id = task['product_id']

        notify_email = task.get('notify_email')

        if isinstance(notify_email, list):
            notify_email = set(notify_email)
        elif notify_email:
            notify_email = {notify_email}
        else:
            notify_email = set()

        alerts = db.alerts.find({'retailer': retailer, 'product_id': product_id})
        for alert in alerts:
            email = alert.get('notify_email')
            if isinstance(email, list):
                notify_email.update(email)
            elif email:
                notify_email.add(email)

        if notify_email:
            product_review = db[retailer].find_one({'product_id': product_id}, sort=[('date', DESCENDING)])

            product_name = None
            product_url = None

            if product_review:
                product_name = product_review.get('product_name')
                product_url = product_review.get('product_url')

            with app.test_request_context(app.config['SERVER_URL']):
                download_url = url_for('download_reviews', retailer=retailer, product_id=product_id,
                                       signature=sign_export(retailer, product_id), format='csv', _external=True)

            group_count = count

            group_products_seen = set()
            group_products_seen.add((retailer, product_id))

            if task.get('group_id'):
                group_id = task['group_id']

                group_processing_tasks = db.tasks.find({
                    'group_id': group_id,
                    'ended_at': None,
                    '_id': {'$ne': task['_id']}  # current task is not updated yet
                }).count()

                if group_processing_tasks:
                    logger.info('Do not send notify: {} group tasks are not finished. Send notify after'.
                                format(group_processing_tasks))
                    return

                with app.test_request_context(app.config['SERVER_URL']):
                    download_group_url = url_for('download_group_reviews', retailer=retailer, group_id=group_id,
                                                 signature=sign_export(retailer, group_id), format='csv',
                                                 _external=True)

                body = u'Download all new reviews: {}\n\n' \
                       u'Item name: {}\n' \
                       u'New reviews: {}\n' \
                       u'Item URL: {}\n' \
                       u'Download reviews: {}\n\n'.format(download_group_url, product_name, count, product_url,
                                                          download_url)

                group_tasks = db.tasks.find({'group_id': group_id, '_id': {'$ne': task['_id']}}).\
                    sort('ended_at', DESCENDING)

                for group_task in group_tasks:
                    group_product_retailer = group_task['retailer']
                    group_product_id = group_task['product_id']

                    if (group_product_retailer, group_product_id) in group_products_seen:
                        # skip old group tasks
                        break

                    group_products_seen.add((group_product_retailer, group_product_id))

                    group_product_count = group_task.get('reviews') or 0
                    group_count += group_product_count

                    if group_product_count:
                        group_product_name = None
                        group_product_url = None

                        group_product_review = db[group_product_retailer].find_one({'product_id': group_product_id},
                                                                                   sort=[('date', DESCENDING)])

                        if group_product_review:
                            group_product_name = group_product_review.get('product_name')
                            group_product_url = group_product_review.get('product_url')

                        with app.test_request_context(app.config['SERVER_URL']):
                            group_download_url = url_for('download_reviews', retailer=group_product_retailer,
                                                         product_id=group_product_id,
                                                         signature=sign_export(group_product_retailer, group_product_id),
                                                         format='csv', _external=True)

                        body += u'Item name: {}\nNew reviews: {}\nItem URL: {}\nDownload reviews: {}\n\n'.format(
                            group_product_name, group_product_count, group_product_url, group_download_url)

                subject = '{} New Reviews for the group: {}'.format(group_count, group_id)

            if not group_count:
                logger.info('Do not send notify: no new reviews')
                return

            if len(group_products_seen) == 1:
                body = 'Item URL: {}\nDownload reviews: {}'.format(product_url, download_url)

                subject = u'{} New Reviews for: {}'.format(count, product_name or product_url)

            ses = boto.connect_ses()
            ses.send_email(source='noreply@contentanalyticsinc.com',
                           subject=subject,
                           body=body,
                           to_addresses=list(notify_email))
    except:
        logger.error('Can not send notify email: {}'.format(traceback.format_exc()))
