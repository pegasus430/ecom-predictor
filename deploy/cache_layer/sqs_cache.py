import os
import sys
import json
import time
import pickle
import datetime
import logging
import logging.config

import redis

CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(2, os.path.join(CWD, '..', 'sqs_ranking_spiders'))
from sqs_queue import SQS_Queue

from cache_starter import log_settings
from simmetrica_class import Simmetrica

CACHE_TASKS_SQS = 'cache_sqs_ranking_spiders_tasks' # received_requests
# CACHE_OUTPUT_QUEUE_NAME = 'cache_sqs_ranking_spiders_output'
# CACHE_PROGRESS_QUEUE = 'cache_sqs_ranking_spiders_progress'
CACHE_OUTPUT_QUEUE_NAME = 'sqs_ranking_spiders_output'
CACHE_PROGRESS_QUEUE = 'sqs_ranking_spiders_progress'

SPIDERS_TASKS_SQS = 'sqs_ranking_spiders_tasks_tests'  # tasks to spiders
SPIDERS_PROGRESS_QUEUE_NAME = 'sqs_ranking_spiders_progress'  # rcvd progress report from spiders 
SPIDERS_OUTPUT_QUEUE_NAME = 'sqs_ranking_spiders_output'

# we will redefine it's in set_logger function after task will be received
logger = None
simmetrica = Simmetrica()

def connect_to_redis_database(timeout=10):
    db = redis.StrictRedis(
        host='sqs-cache.4a6nml.0001.use1.cache.amazonaws.com',
        port=6379,
        socket_timeout=timeout  # if DB is down, everything won't freeze
    )
    #db = redis.StrictRedis(host='localhost', port=6379, db=0)
    return db


def receive_task_from_server(queue_name=CACHE_TASKS_SQS):
    input_queue = SQS_Queue(queue_name)
    if not input_queue.conn or not input_queue.q:
        print("Task queue not exist or cannot connect to amazon SQS.")
        return
    if not input_queue.empty():
        try:
            message = input_queue.get()
            input_queue.task_done()  #### Uncomment this for production
            message = json.loads(message)
            return message
        except:
            pass
    return


def get_data_from_cache_hash(hash_name, key, database):
    # responses_store = {
    #    'term/url:site:arguments': '(time:response)'}
    # requests_store = {
    #    'term/url:site:arguments': '[(time:server), (time:server)]'}
    return database.hget(hash_name, key)


def add_data_to_cache_hash(hash_name, key, value, database):
    return database.hset(hash_name, key, value)


def put_message_into_sqs(message, sqs_name):
    if not isinstance(message, (str, unicode)):
        message = json.dumps(message)
    sqs_queue = SQS_Queue(sqs_name)
    if getattr(sqs_queue, 'q', '') is None:  # SQS with this name don't exist
        logger.warning(
            "Queue {name} not exist. Create new one".format(name=sqs_name))
        try:
            sqs_queue.conn.create_queue(sqs_name)
        # For some reason queue was deleted and we should wait for 60 seconds
        except:
            time.sleep(62)
            sqs_queue.conn.create_queue(sqs_name)
        time.sleep(5)
        sqs_queue = SQS_Queue(sqs_name)
    try:
        sqs_queue.put(message)
    except Exception, e:
        logger.error("Failed to put message to queue %s:\n%s",
            sqs_name, str(e))


def check_task_status(sqs_name):
    sqs_queue = SQS_Queue(sqs_name)
    status = None
    if sqs_queue.q is None or sqs_queue.empty():
        # There is no results yet
        return status
    try:
        status = sqs_queue.get()
        sqs_queue.task_done()
    except IndexError:
        pass
    return status


def get_spiders_results(sqs_name):
    logger.info("Get spiders results from {sqs}".format(sqs=sqs_name))
    output = None
    sqs_queue = SQS_Queue(sqs_name)
    attemps = 0
    while attemps < 20:
        if sqs_queue.q is None:
            logger.error("Queue %s doesn't exist" % sqs_name)
            time.sleep(5)
            sqs_queue = SQS_Queue(sqs_name)
            continue
        try:
            output = sqs_queue.get()
            sqs_queue.task_done()
        except Exception as e:
            logger.info(str(e))
            attemps += 1
            time.sleep(5)
            sqs_queue = SQS_Queue(sqs_name)
            continue
        else:
            break
    return output


def pickle_results(data):
    logger.info("Pickle data")
    pickled_data = pickle.dumps((time.time(), data))
    return pickled_data


def unpickle_data(data):
    logger.info("Unpickle data")
    timestamp, decompressed_data = pickle.loads(data)
    return timestamp, decompressed_data


def put_results_into_cache(task_stamp, data, hash_name, database):
    database.hmset(hash_name, {task_stamp: data})


def load_cache_response_to_sqs(data, sqs_name):
    for part in data:
        put_message_into_sqs(part, sqs_name)


def generate_task_stamp(task_message):
    site = task_message['site']
    url = task_message.get('url')
    additional_part = ''
    if url:
        additional_part = 'url:%s' % url
    searchterms_str = task_message.get('searchterms_str')
    if searchterms_str:
        additional_part = 'st:%s' % searchterms_str
        cmd_args = task_message.get('cmd_args', {})
        if cmd_args:
            keys = cmd_args.keys()
            keys.sort()
            for key in keys:
                additional_part += ':{key}:{value}'.format(
                    key=key,
                    value=cmd_args[key]
                )
    stamp = "{site}:{additional_part}".format(
        site=site,
        additional_part=additional_part
    )
    branch_name = task_message.get('branch_name')
    if branch_name:
        stamp += ':branch:%s' % branch_name
    return stamp


def send_status_back_to_server(status, server_name, task_id=None):
    msg = {
        "_msg_id": str(task_id),
        "utc_datetime": datetime.datetime.utcnow().isoformat(),
        "progress": status
    }
    queue_name = server_name + CACHE_PROGRESS_QUEUE
    put_message_into_sqs(msg, queue_name)


def get_orig_queue(queue):
    """return queue name without "cache_" part at the beginning"""
    cache_part = 'cache_'
    if queue.startswith(cache_part):
        return queue[len(cache_part):]
    else:
        return queue


def generate_and_handle_new_request(task_stamp, task_message, cache_db,
                                    queue, forced=False):
    logger.info("Generate and handle new request")
    response_will_be_provided_by_another_daemon = False
    task_id = task_message['task_id']
    server_name = task_message['server_name']
    request_item = (time.time(), server_name)
    last_request = get_data_from_cache_hash(
        'last_request', task_stamp, cache_db)

    # check what was the latest sent to SQS request for this task
    if last_request:  # request hash entry existing in database
        logger.info("Last request was found")
        # last Request is older than 1 hour
        logger.info("time %s", time.time())
        logger.info("last request time %s", float(last_request))
        if (time.time() - float(last_request) > 3600) or forced:
            logger.info("Last request is very old")
            logger.info("Provide new task to spiders SQS")
            put_message_into_sqs(task_message, get_orig_queue(queue))
            send_status_back_to_server(
                "Request for this task was found but it was sent more than 1 "
                "hour ago.", server_name, task_id)
            send_status_back_to_server(
                "Redirect request to spiders sqs.", server_name, task_id)
            add_data_to_cache_hash(
                'last_request', task_stamp, time.time(), cache_db)
        else:
            logger.info("Last request fresh enough")
            send_status_back_to_server("Wait for request from other instance.",
                                       server_name, task_id)
            response_will_be_provided_by_another_daemon = True
    else:
        logger.info("Last request wasn't found in cache. Create new one.")
        put_message_into_sqs(task_message, get_orig_queue(queue))
        send_status_back_to_server("Redirect request to spiders sqs.",
                                   server_name, task_id)
        add_data_to_cache_hash('last_request', task_stamp,
                               time.time(), cache_db)

    # add request to waiting list in any case
    logger.info("Add request to waiting list")
    requests = get_data_from_cache_hash('requests', task_stamp, cache_db)
    if requests:  # request hash entry existing in database
        requests = pickle.loads(requests)
    else:
        requests = []
    requests.append(request_item)
    pickled_requests = pickle.dumps(requests)
    add_data_to_cache_hash('requests', task_stamp, pickled_requests, cache_db)
    if response_will_be_provided_by_another_daemon:
        sys.exit()

    spiders_progress_queue = server_name + SPIDERS_PROGRESS_QUEUE_NAME
    spiders_output_queue = server_name + SPIDERS_OUTPUT_QUEUE_NAME

    counter = 0
    logger.info("Check for spider status")
    while True:
        queue_name = server_name + CACHE_PROGRESS_QUEUE
        status = check_task_status(spiders_progress_queue)
        if status and 'failed' in status:
            counter += 1
            if counter <= 3:
                logger.warning("Receive failed status. Restart spider.")
                put_message_into_sqs(task_message, get_orig_queue(queue))
                continue
            else:
                logger.error("Spider still not working. Exit.")
                put_message_into_sqs(status, queue_name)
                sys.exit()
        elif status:
            put_message_into_sqs(status, queue_name)
            if 'finished' in status:
                break

    output = get_spiders_results(spiders_output_queue)
    if not output:
        logger.error("Don't receive output from spider")
        sys.exit()

    pickled_output = pickle_results(output)
    logger.info("Pickled output: %s", pickled_output) ##########
    logger.info("Update response object for this search term in cache")
    put_results_into_cache(
        task_stamp, pickled_output, 'responses', cache_db)

    logger.info("Renew requests list")
    requests = get_data_from_cache_hash('requests', task_stamp, cache_db)
    requests = pickle.loads(requests)
    logger.info("Return data to all requests/servers")
    counter = 0
    while requests:
        item = requests.pop()
        logger.info("Request: %s", item)
        server_name = item[1]
        cache_output_queue = server_name + CACHE_OUTPUT_QUEUE_NAME
        logger.info("Uploading response data to server queue")
        put_message_into_sqs(output, cache_output_queue)
        send_status_back_to_server("finished", server_name, task_id)
        simmetrica.set_time_of_newest_resp()
        simmetrica.set_time_of_oldest_resp()
        if counter >= 1:
            simmetrica.increment_returned_resp_set(task_stamp)
        counter += 1
        
    logger.info("Update requests database entry with blank requests list")
    requests = pickle.dumps(requests)
    cache_db.hmset('requests', {task_stamp: requests})
    cache_db.hdel('last_request', task_stamp)


def set_logger(task_message):
    global logger
    task_id = task_message['task_id']
    log_file_path = '/tmp/cache_logs/%s_sqs_cache' % task_id
    log_settings['handlers']['to_log_file']['filename'] = log_file_path
    logging.config.dictConfig(log_settings)
    logger = logging.getLogger('cache_log')


def main(queue_name):
    cache_db = connect_to_redis_database()
    attemps = 0
    while attemps < 3:
        task_message = receive_task_from_server(queue_name)   
        if not task_message:
            attemps += 1
            time.sleep(1)
            continue
        break
    else:
        # no any messages was found - this is duplicated instance
        sys.exit()
    set_logger(task_message)
    logger.info("Task was successfully received:\n%s", task_message)
    status = "Ok. Task was received."
    server_name = task_message['server_name']
    task_id = task_message['task_id']
    send_status_back_to_server(status, server_name, task_id)
    simmetrica.increment_received_req_set()

    logger.info("Generate task stamp for task")
    task_stamp = generate_task_stamp(task_message)
    logger.debug("Task stamp:     %s", task_stamp)

    forced = bool(task_message.get('forced_task'))
    if forced:
        logger.info("Forced task was received")
        generate_and_handle_new_request(
            task_stamp, task_message, cache_db, queue_name, forced)
        sys.exit()

    freshness = task_message.get('freshness')
    if freshness:
        freshness = float(freshness) * 3600
    if not freshness:
        freshness = 60*60  # one hour

    response = get_data_from_cache_hash('responses', task_stamp, cache_db)
    if response:
        logger.info("Use existing response")
        timestamp, output = unpickle_data(response)
        # all comparison performed in seconds.
        if time.time() - timestamp < int(freshness):
            logger.info("Existing response fresh enough")
            # change _msg_id for output msg
            json_output = json.loads(output)
            json_output['_msg_id'] = task_message.get('task_id', None)
            json_output['cached'] = True
            cache_output_queue = server_name + CACHE_OUTPUT_QUEUE_NAME
            logger.info("Uploading response data to servers queue")
            put_message_into_sqs(json_output, cache_output_queue)
            send_status_back_to_server("finished", server_name, task_id)
            simmetrica.increment_returned_resp_set(task_stamp)
        # Response exist but it's too old
        else:
            logger.info("Existing response not satisfy freshness")
            generate_and_handle_new_request(
                task_stamp, task_message, cache_db, queue_name)
    # Response not exist at all
    else:
        logger.info("Existing response wasn't found for this task")
        generate_and_handle_new_request(
            task_stamp, task_message, cache_db, queue_name)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        queue_name = sys.argv[1].strip()
    else:
        queue_name = CACHE_TASKS_SQS
    main(queue_name)
