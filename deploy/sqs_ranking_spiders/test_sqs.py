import json
import sys
from time import sleep
from datetime import datetime, timedelta
from random import randint
from boto.sqs.message import Message
from boto.sqs import connect_to_region as connect_sqs
from boto.s3 import connect_to_region as connect_s3

import logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='[%(asctime)s, %(levelname)s] %(message)s',
)
logging.getLogger('boto').setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)


def generate_tasks():
    """
    returns dictionaries with tasks to be pushed to sqs
    keys of dictionary are ids for the task
    """
    tasks = [
        dict(site='jcpenney',
             searchterms_str='jeans',
             cmd_args=dict(quantity=100)),  # quantity

        dict(site='walmart',
             searchterms_str='iphone',
             with_best_seller_ranking=True,
             cmd_args=dict(quantity=50)),  # best seller & quantity

        dict(site='amazon',
             url='http://www.amazon.com/Casio-MQ24-1E-Black-Resin-Watch/dp/'
                 'B000GAWSHM/ref=sr_1_2?ie=UTF8&qid=1447922212&sr=8-2'),  # url

        dict(site='amazon',
             searchterms_str='\xd1\x87\xd0\xb0\xd1\x81\xd1\x8b',
             cmd_args=dict(quantity=100)),  # non ascii 1

        dict(site='amazon',  # non ascii 2 & no quantity
             searchterms_str=u'\u30ad\u30e4\u30ce\u30f3'),

        dict(site='kohls',
             searchterms_str='book',
             cmd_args=dict(quantity=100, save_raw_pages=True)),  # save s3 cache

        dict(site='target',
             searchterms_str='chair',
             cmd_args=dict(quantity=100),
             branch_name='master'),  # branch

        dict(site='walmart_shelf_urls',
             url='http://www.walmart.com/search/?query=dress',
             cmd_args=dict(num_pages=10)),  # shelf

        dict(site='jcpenney_coupons',
             url='http://www.jcpenney.com/jsp/browse/marketing/'
                 'promotion.jsp?pageId=pg40027800029#'),  # coupon
    ]
    tasks_dict = {}
    for task in tasks:
        random_id = randint(10000, 9000000)
        task['task_id'] = random_id
        tasks_dict[str(random_id)] = task
    logger.info('Task ids: %s', tasks_dict.keys())

    return tasks_dict


def validate_tasks(tasks):
    """make sure all tasks contain required fields"""
    res = True
    required_fields = ['task_id', 'site', 'server_name',
                       ['url', 'urls', 'searchterms_str']]
    for task in tasks.itervalues():
        for field in required_fields:
            if isinstance(field, basestring):
                if field not in task:
                    logger.warning('Validation error: task %s, missing %s',
                                   task, field)
                    res = False
            else:
                for sub_field in field:
                    if sub_field in task:
                        break
                else:
                    logger.warning('Validation error: task %s, missing any: %s',
                                   task, field)
                    res = False
    return res


def add_additional_task_params(tasks, add_to_cmd_args=False, **params):
    """add some parameters to the tasks"""
    for task in tasks.itervalues():
        if add_to_cmd_args:
            if 'cmd_args' not in task:
                task['cmd_args'] = {}
            task['cmd_args'].update(params)
        else:
            task.update(params)


def get_or_create_sqs_queue(conn, queue_name):
    """create and return sqs queue"""
    try:
        queue = conn.get_queue(queue_name)
        if not queue:
            raise Exception
    except Exception:
        logger.info('Queue %s not exists, creating it', queue_name)
        queue = conn.create_queue(queue_name)
        sleep(10)
    return queue


def push_tasks_to_sqs(tasks, queue):
    """put tasks to sqs queue"""
    logger.info('Pushing tasks to sqs')
    for task in tasks.itervalues():
        data = json.dumps(task)
        m = Message(body=data)
        queue.write(m)


def get_message_from_queue(queue, wait_time):
    """read and delete one message from given queue (if any)"""
    msg = queue.read(wait_time)
    if msg:
        data = json.loads(msg.get_body())
        queue.delete_message(msg)
        return data


def check_s3_key(bucket, key):
    """returns True if key exists and not empty, else False"""
    item = bucket.lookup(key)
    if item and item.size:
        return True
    logger.warning('S3 key not exists or empty: %s', key)
    return False


def check_tasks_completed(tasks, wait_minutes, output_queue, s3_bucket):
    """check all pushed tasks to be completed"""
    step_time = 10
    time_start = datetime.now()
    time_end = time_start + timedelta(minutes=wait_minutes)
    res = False
    logger.info('Starting to check output queue')
    while True:
        logging.debug('Check status next step')
        if datetime.now() >= time_end:
            break  # stop when allowed time is passed
        message = get_message_from_queue(output_queue, step_time)
        if not message:
            sleep(5)
            continue  # wait some time before another try
        task_id = str(message['_msg_id'])
        res = check_s3_key(s3_bucket, message['s3_key_data'])
        if res:  # if data exists in s3 (ok)
            tasks.pop(task_id, None)
        if not tasks:
            res = True  # return True only when all tasks finished working
            break
    logger.info('Finished checking output in %s', datetime.now() - time_start)
    return res


def log_failed_tasks(tasks):
    if not tasks:
        logger.info('All tasks finished')
        return
    logger.warning('Some tasks not finished in time')
    for task in tasks.itervalues():
        logger.warning(task)


def main():
    logger.info('Initializing variables')
    sqs_conn = connect_sqs('us-east-1')
    s3_conn = connect_s3('us-east-1')
    bucket = s3_conn.get_bucket('spyder-bucket')
    max_wait_minutes = 40
    server_name = 'sqs_test'
    sqs_name = 'sqs_ranking_spiders'
    output_queue_name = '%s%s_output' % (server_name, sqs_name)
    progress_queue_name = '%s%s_progress' % (server_name, sqs_name)
    output_queue = get_or_create_sqs_queue(sqs_conn, output_queue_name)
    progress_queue = get_or_create_sqs_queue(sqs_conn, progress_queue_name)
    tasks_queue = get_or_create_sqs_queue(sqs_conn, '%s_tasks_tests' % sqs_name)

    tasks = generate_tasks()
    # we never store and retrieve data to/from cache
    add_additional_task_params(
        tasks, sqs_cache_save_ignore=True, sqs_cache_get_ignore=True,
        server_name=server_name)
    if not validate_tasks(tasks):
        logger.error('Tasks validation failed, aborting')
        return

    push_tasks_to_sqs(tasks, tasks_queue)
    res = check_tasks_completed(tasks, max_wait_minutes, output_queue, bucket)
    log_failed_tasks(tasks)


if __name__ == '__main__':
    main()