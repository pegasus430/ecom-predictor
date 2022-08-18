
# TODO:
# ...

import os
import sys
import random
import time
import json
import zipfile

import boto
import boto.sqs
from boto.s3.connection import S3Connection

CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(1, os.path.join(CWD, '..'))

from sqs_ranking_spiders import QUEUES_LIST

try:
    # try local mode (we're in the deploy dir)
    from sqs_ranking_spiders.remote_instance_starter import AMAZON_BUCKET_NAME

except ImportError:
    # we're in /home/spiders/repo
    from repo.remote_instance_starter import AMAZON_BUCKET_NAME


MAX_WORKING_TIME = 30  # 30 mins
LOCAL_DUMP_PATH = '/tmp/_test_sqs_messages'
REGION = "us-east-1"
DELETE_MESSAGES = True  # set False to avoid deleting messages in output queues


def _get_conn():
    conn = boto.sqs.connect_to_region(REGION)
    return conn


def _get_sqs_queue(queue_name):
    conn = _get_conn()
    return conn.get_queue(queue_name)


def _create_sqs_queue(queue_name, visib_timeout=30):
    conn = _get_conn()
    try:
        return conn.create_queue(queue_name, visib_timeout)
    except Exception, e:
        print str(e)


def _read_queue(queue_name):
    """ Returns all the messages in the queue """
    queue = _get_sqs_queue(queue_name)
    if queue is None:
        return []  # the queue has not been created yet (?)
    return queue.get_messages(
        num_messages=10, visibility_timeout=3
    )


def get_sqs_messages(queue_name):
    """ Turns messages into files """
    def dump_message(message):
        if not os.path.exists(LOCAL_DUMP_PATH):
            os.makedirs(LOCAL_DUMP_PATH)
        fname = str(random.randint(1000000, 2000000))
        if not isinstance(message, (str, unicode)):
            message = json.dumps(message.get_body())
        fname = os.path.join(LOCAL_DUMP_PATH, fname)
        with open(fname, 'w') as fh:
            fh.write(message)
        return fname

    queue = _get_sqs_queue(queue_name)
    for message in _read_queue(queue_name):
        fname = dump_message(message)
        if DELETE_MESSAGES:
            queue.delete_message(message)
        yield fname


def read_msgs_until_task_id_appears(task_id, queue_name, max_wait_time=30*60):
    for sec in range(max_wait_time):
        time.sleep(1)
        for fname in list(get_sqs_messages(queue_name)):
            with open(fname, 'r') as fh:
                msg_data = json.loads(fh.read())
            # may still be string due to double json encoding on dumps()
            if isinstance(msg_data, (str, unicode)):
                msg_data = json.loads(msg_data)
            task_id_sqs = msg_data['_msg_id']
            if str(task_id) == str(task_id_sqs):
                return fname, msg_data


def download_s3_file(bucket, s3_path, local_path):
    aws_connection = S3Connection()
    bucket = aws_connection.get_bucket(bucket)
    key = bucket.get_key(s3_path)
    key.get_contents_to_filename(local_path)


def validate_data_file(fname, validated_fileld, field_pattern):
    """ Checks the local data file (downloaded from S3) """
    all_lines_are_jsons = True
    with open(fname, 'r') as fh:
        for line_no, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                line = json.loads(line)
            except Exception, e:
                print 'LINE %i is not JSON!' % line_no
                all_lines_are_jsons = False
                continue
            if field_pattern:
                if line.get(validated_fileld, '') != field_pattern:
                    print ('%s DO NOT MARCH AT LINE %i' %
                        (validated_fileld.upper(), line_no))
                    return False
            else:
                if not validated_fileld in line:
                    print ('%s DO NOT EXIST AT THE LINE %i' %
                           (validated_fileld.upper(), line_no))
                    return False
    return all_lines_are_jsons


def is_plain_jsonlist_file(fname):
    with open(fname, 'r') as fh:
        cont = fh.read(1024)
    if not cont:
        return
    return cont[0] == '{'


def unzip_file(file_path, unzip_path=LOCAL_DUMP_PATH):
    zf = zipfile.ZipFile(file_path, allowZip64=True)
    content_fielname = zf.namelist()[0]
    path = os.path.dirname(unzip_path)
    zf.extractall(path)
    unzipped_file_path = os.path.join(path, content_fielname)
    return unzipped_file_path


def main_loop(flag):
    additional_commands = {
        'search_term': ' searchterms_str=%s',
        'test_single_result': ' product_url=%s',
        'test_best_seller_ranking': (
            ' searchterms_str=%s with_best_seller_ranking=True')
    }
    additional_args = {
        'search_term': 'asus',
        'test_single_result': (
            'http://www.amazon.com/Panasonic-Expandable-Cordless-KX-'
            'TG6512B-Handsets/dp/B0036D9YKU/ref=sr_1_4?ie=UTF8&qid='
            '1428478402&sr=8-4&keywords=phone'
        ),
        'test_best_seller_ranking': 'laptop'
    }
    validated_fields = {
        'search_term': 'search_term',
        'test_single_result': 'is_single_result',
        'test_best_seller_ranking': 'best_seller_ranking'
    }
    search_term = additional_args[flag]
    fields_patterns = {
        'search_term': search_term,
        'test_single_result': True,
        'test_best_seller_ranking': None
    }
    test_server_name = 'test_server'
    test_queue_name = QUEUES_LIST['test']
    local_data_file = '/tmp/_s3_data_file.zip'
    # create output 'queues' for this server
    _create_sqs_queue(test_server_name+'sqs_ranking_spiders_progress',
                      visib_timeout=30)
    _create_sqs_queue(test_server_name+'sqs_ranking_spiders_output',
                      visib_timeout=30)

    # 0. Generate random marker to identify the test task
    random_id = str(random.randint(100000, 200000))
    print 'RANDOM ID FOR THIS TASK:', random_id

    # 1. Create a new message in the input queue to start crawling
    cmd = ('python add_task_to_sqs.py task_id=%s'
           ' server_name=%s')
    cmd = cmd % (random_id, test_server_name)
    cmd += additional_commands[flag] % additional_args[flag]
    print '    ...executing:', cmd
    os.system(cmd)

    # 2. Read the progress queue and validate it
    progress_result = read_msgs_until_task_id_appears(
        random_id, test_server_name+'sqs_ranking_spiders_progress')
    if progress_result is None:
        print 'Progress queue failed!'
        sys.exit()
    fname, msg_data = progress_result
    print 'Progress queue first message:', msg_data
    assert 'progress' in msg_data

    # 3. Read the output queue and get the S3 bucket filename
    output_result = read_msgs_until_task_id_appears(
        random_id, test_server_name+'sqs_ranking_spiders_output')
    if output_result is None:
        print 'Data queue failed!'
        sys.exit()
    fname, msg_data = output_result
    print 'Data queue first message:', msg_data
    assert 's3_key_data' in msg_data

    # 4. Read the S3 bucket file and validate its content
    download_s3_file(
        AMAZON_BUCKET_NAME, msg_data['s3_key_data'], local_data_file)
    if not is_plain_jsonlist_file(local_data_file):
        assert zipfile.is_zipfile(local_data_file), \
            'data file was received not in zip!'
        local_data_file = unzip_file(local_data_file)
    if not is_plain_jsonlist_file(local_data_file):
        assert False, 'Failed to unzip data file!'
    validator = validate_data_file(
        local_data_file,
        validated_fileld=validated_fields[flag],
        field_pattern=fields_patterns[flag]
        )
    if validator:
        print 'EVERYTHING IS OK'
        # removed unzipped data file
        os.system('rm %s' % local_data_file)
    else:
        print 'DATA FILE CHECK FAILED'


if __name__ == '__main__':
    print("\nCheck SQS with search term")
    main_loop('search_term')
    print("\nCheck SQS with single product_url")
    main_loop('test_single_result')
    print("\nCHeck SQS with search term and best_seller_ranking flag")
    main_loop('test_best_seller_ranking')
