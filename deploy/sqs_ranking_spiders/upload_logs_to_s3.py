import json
import os
import sys

import boto
from boto.s3.key import Key


CWD = os.path.dirname(os.path.abspath(__file__))
path = os.path.expanduser('~/repo')
#for local development
sys.path.insert(1, os.path.join(CWD, '..'))
#for server side
sys.path.insert(1, os.path.join(path, '..'))
from sqs_ranking_spiders.task_id_generator import \
    generate_hash_datestamp_data, load_data_from_hash_datestamp_data
try:
    # try local mode
    from sqs_ranking_spiders.remote_instance_starter import log_file_path,\
        logging, AMAZON_BUCKET_NAME
except ImportError:
    # we're in /home/spiders/repo
    from repo.remote_instance_starter import log_file_path, logging, \
        AMAZON_BUCKET_NAME

logger = logging.getLogger('main_log')
log_mod_time_flag_path = '/tmp/log_mod_time_flag'

RANDOM_HASH = None
DATESTAMP = None
FOLDERS_PATH = None


def set_global_variables_from_data_file():
    try:
        json_data = load_data_from_hash_datestamp_data()
        global RANDOM_HASH, DATESTAMP, FOLDERS_PATH
        RANDOM_HASH = json_data['random_hash']
        DATESTAMP = json_data['datestamp']
        FOLDERS_PATH = json_data['folders_path']
    except:
        generate_hash_datestamp_data()
        set_global_variables_from_data_file()

def upload_logs_into_s3(bucket_name):
    global RANDOM_HASH, DATESTAMP, FOLDERS_PATH
    conn = boto.connect_s3(is_secure=False)
    bucket = conn.get_bucket(bucket_name, validate=False)
    # Cut out file name
    log_filename = DATESTAMP + '____' + RANDOM_HASH + '____' + \
        os.path.basename(log_file_path)
    # Generate file path for S3
    folders = (FOLDERS_PATH + log_filename)
    k = Key(bucket)
    # Set path to file on S3
    k.key = folders
    try:
        # Upload file to S3
        k.set_contents_from_filename(log_file_path)
    except Exception:
        pass
        logger.error("Failed to load log files to S3. "
                     "Check file path and amazon keys/permissions.")

def check_last_log_file_was_uploaded():
    statbuf = os.stat(log_file_path)
    last_file_mod = str(statbuf.st_mtime)
    try:
        f = open(log_mod_time_flag_path, 'r')
        last_uploaded_mod = f.read()
        f.close()
    # log_mod_time_flag wasn't created yet. No any uploads to amazon
    except:
        last_uploaded_mod = "File wasn't uploaded yet"
    finally:
        # rewrite or create log_mod_time_flag in any case
        f = open(log_mod_time_flag_path, 'w')
        f.write(last_file_mod)
        f.close()
    filesize = os.path.getsize(log_file_path)
    if last_file_mod != last_uploaded_mod and filesize > 0:
        return False
    return True


if __name__ == '__main__':
    if not check_last_log_file_was_uploaded():
        set_global_variables_from_data_file()
        upload_logs_into_s3(AMAZON_BUCKET_NAME)
