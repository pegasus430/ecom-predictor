from __future__ import division, unicode_literals
import os
import re
import sys
import time
import json
import random
import zipfile
import unidecode
import urlparse
import string
import traceback
import redis
import boto
import pprint
import requests
import psutil
import resource
from re import sub
from boto.utils import get_instance_metadata
from boto.s3.key import Key
from collections import OrderedDict
import datetime
import traceback
from threading import Thread
from multiprocessing.connection import Listener, AuthenticationError, Client
from subprocess import Popen, PIPE, check_output, CalledProcessError, STDOUT

# list of all available incoming SQS with tasks
OUTPUT_QUEUE_NAME = 'sqs_ranking_spiders_output'
PROGRESS_QUEUE_NAME = 'sqs_ranking_spiders_progress'  # progress reports
JOB_OUTPUT_PATH = '~/job_output'  # local dir
CWD = os.path.dirname(os.path.abspath(__file__))
path = os.path.expanduser('~/repo')
# for local mode
sys.path.insert(1, os.path.join(CWD, '..'))
sys.path.insert(2, os.path.join(CWD, '..', '..', 'special_crawler',
                                'queue_handler'))
sys.path.insert(2, os.path.join(CWD, '..', '..', 'product-ranking'))

# for servers path
sys.path.insert(1, os.path.join(path, '..'))
sys.path.insert(2, os.path.join(path, '..', '..', 'special_crawler',
                                'queue_handler'))
sys.path.insert(3, os.path.join(path, 'tmtext', 'product-ranking'))

# WORKAROUND: Import spiders_shared_code.utils
import spiders_shared_code
import imp
path = os.path.join(os.path.abspath(__file__).rsplit(os.sep, 1)[0],
                    '..', '..', 'spiders_shared_code', 'utils.py')
spiders_shared_code.utils = imp.load_source("spiders_shared_code.utils", path)
# END WORKAROUND


# for loghistory
sys.path.append(os.path.join(CWD, '..', '..', 'spiders_shared_code', 'product-ranking'))
from spiders_shared_code.log_history import LogHistory


from sqs_ranking_spiders.task_id_generator import \
    generate_hash_datestamp_data, load_data_from_hash_datestamp_data

try:
    # try local mode (we're in the deploy dir)
    from sqs_ranking_spiders.remote_instance_starter import REPO_BASE_PATH, \
        logging, AMAZON_BUCKET_NAME
    from sqs_ranking_spiders import QUEUES_LIST
except ImportError:
    # we're in /home/spiders/repo
    from repo.remote_instance_starter import REPO_BASE_PATH, logging, \
        AMAZON_BUCKET_NAME
    from repo.remote_instance_starter import QUEUES_LIST
from product_ranking import statistics

sys.path.insert(
    3, os.path.join(REPO_BASE_PATH, 'deploy', 'sqs_ranking_spiders'))

from sqs_queue import SQS_Queue
from libs import convert_json_to_csv
from cache_layer import REDIS_HOST, REDIS_PORT, INSTANCES_COUNTER_REDIS_KEY, \
    JOBS_STATS_REDIS_KEY, JOBS_COUNTER_REDIS_KEY

TEST_MODE = False  # if we should perform local file tests

logger = logging.getLogger('main_log')

RANDOM_HASH = None
DATESTAMP = None
FOLDERS_PATH = None

CONVERT_TO_CSV = True

# Connect to S3
try:
    S3_CONN = boto.connect_s3(is_secure=False)
except:
    pass
# uncomment if you are not using ssl

# Get current bucket
try:
    S3_BUCKET = S3_CONN.get_bucket(AMAZON_BUCKET_NAME, validate=False)
except:
    pass
# settings
MAX_SLOTS = 50  # concurrent tasks per instance, all with same git branch
MAX_TRIES_TO_GET_TASK = 100  # tries to get max tasks for same branch
LISTENER_ADDRESS = ('localhost', 9070)  # address to listen for signals
# SCRAPY_LOGS_DIR = ''  # where to put log files
# SCRAPY_DATA_DIR = ''  # where to put scraped data files
# S3_UPLOAD_DIR = ''  # folder path on the s3 server, where to save logs/data
STATUS_STARTED = 'opened'
STATUS_FINISHED = 'closed'
SIGNAL_SCRIPT_OPENED = 'script_opened'
SIGNAL_SCRIPT_CLOSED = 'script_closed'
SIGNAL_SPIDER_OPENED = 'spider_opened'
SIGNAL_SPIDER_CLOSED = 'spider_closed'

# required signals
REQUIRED_SIGNALS = [
    # [signal_name, wait_in_seconds]
    [SIGNAL_SCRIPT_OPENED, 3 * 60],  # wait for signal that script started
    [SIGNAL_SPIDER_OPENED, 1 * 60],
    [SIGNAL_SPIDER_CLOSED, 5 * 60 * 60],
    [SIGNAL_SCRIPT_CLOSED, 1 * 160]
]

## optional extension signals
EXTENSION_SIGNALS = {
    'cache_downloading': 30 * 60,  # cache load FROM s3
    'cache_uploading': 30 * 60  # cache load TO s3,
}

from cache_settings import (CACHE_HOST, CACHE_URL_GET, CACHE_URL_SAVE,
                            CACHE_URL_STATS, CACHE_URL_FAIL, CACHE_AUTH,
                            CACHE_TIMEOUT, CACHE_GET_IGNORE_KEY, CACHE_SAVE_IGNORE_KEY)

# File with required parameters for restarting scrapy daemon.
OPTION_FILE_FOR_RESTART = '/tmp/scrapy_daemon_option_file.json'
# Allow to restart scrapy daemon
ENABLE_TO_RESTART_DAEMON = True


# custom exceptions
class FlowError(Exception):
    """base class for new custom exceptions"""
    pass


class ConnectError(FlowError):
    """failed to connect to scrapy process in allowed time"""
    pass


class FinishError(FlowError):
    """scrapy process didn't finished in allowed time"""
    pass


class SignalSentTwiceError(FlowError):
    """same signal came twice"""
    pass


class SignalTimeoutError(FlowError):
    """signal didn't finished in allowed time"""
    pass


def get_branch_for_task(task_data):
    return task_data.get('branch_name')


class GlobalSettingsFromRedis(object):
    """settings cache"""

    __settings = None

    @classmethod
    def get_global_settings_from_sqs_cache(cls):
        if cls.__settings is None:
            try:
                from cache_layer.cache_service import SqsCache
                sqs = SqsCache()
                logger.info('Getting global settings from redis cache.')
                cls.__settings = sqs.get_settings()
            except Exception as e:
                cls.__settings = {}
                logger.error(
                    'Error while get global settings from redis cache.'
                    ' ERROR: %s', str(e))
        return cls.__settings

    def get(self, key, default=None):
        return self.get_global_settings_from_sqs_cache().get(key, default)


global_settings_from_redis = GlobalSettingsFromRedis()

def get_instance_log_path(path):
    logger.debug('path get_instance_log_path: {}'.format(path))
    try:
        path = path.split("/")[-1]
        date_raw = path.split("____")[0]
        date = date_raw.split("-")
        formatted_date = "{}/{}/{}/{}".format(date[2], date[1], date[0], date_raw)
        instance_id = path.split("____")[1]
        instance_log = "http://sqs-tools.contentanalyticsinc.com/" \
                       "get-file/?file={}____{}____remote_instance_starter2.log".format(formatted_date, instance_id)
    except:
        logger.error('Error in get_instance_log_path: {}'.format(traceback.format_exc()))

        return None
    else:
        return instance_log

def get_instance_id_from_path(path):
    logger.debug('path get_instance_id_from_path: {}'.format(path))
    try:
        instance_id = path.split("____")[1]
    except:
        logger.error('Error in get_instance_id_from_path: {}'.format(traceback.format_exc()))
        return None
    else:
        return instance_id

def get_actual_branch_from_cache():
    logger.info('Get default branch from redis cache.')
    branch = global_settings_from_redis.get('remote_instance_branch',
                                            'sc_production')
    logger.info('Got branch name from cache %s', branch)
    return branch or 'sc_production'


def switch_branch_if_required(metadata):
    default_branch = get_actual_branch_from_cache()
    branch_name = metadata.get('branch_name', default_branch)
    if branch_name:
        logger.info("Checkout to branch %s", branch_name)
        cmd = ('git fetch --all && git checkout -f {branch} && git pull origin {branch} && '
               'git checkout {default_branch} -- task_id_generator.py && '
               'git checkout {default_branch} -- remote_instance_starter.py &&'
               ' git checkout {default_branch} -- upload_logs_to_s3.py')
        cmd = cmd.format(branch=branch_name, default_branch=default_branch)
        logger.info("Run command '%s'", cmd)
        os.system(cmd)


def is_same_branch(b1, b2):
    return b1 == b2


def slugify(s):
    output = ''
    for symbol in s:
        if symbol.lower() not in string.lowercase and not \
                        symbol.lower() in string.digits:
            output += '-'
        else:
            output += symbol
    output = output.replace(' ', '-')
    while '--' in output:
        # to avoid reserved double-minus chars
        output = output.replace('--', '-')
    return output


def connect_to_redis_database(redis_host, redis_port, timeout=10):
    if TEST_MODE:
        print 'Simulating connect to redis'
        return
    try:
        db = redis.StrictRedis(host=redis_host, port=redis_port,
                               socket_timeout=timeout)
    except Exception as e:
        logger.warning("Failed connect to redis database with exception %s", e)
        db = None
    return db


def increment_metric_counter(metric_name, redis_db):
    """This method will just increment reuired key in redis database
    if connecntion to the database exist."""
    if TEST_MODE:
        print 'Simulate redis incremet, key is %s' % metric_name
        return
    if redis_db:
        try:
            redis_db.incr(metric_name)
        except Exception as e:
            logger.warning("Failed to increment redis metric '%s' "
                           "with exception '%s'", metric_name, e)


def read_msg_from_sqs(queue_name_or_instance, timeout=None, attributes=None):
    if isinstance(queue_name_or_instance, (str, unicode)):
        sqs_queue = SQS_Queue(queue_name_or_instance)
    else:
        sqs_queue = queue_name_or_instance
    if not sqs_queue.q:
        logger.error("Task queue '%s' not exist at all",
                     queue_name_or_instance)
        return
    if sqs_queue.count() == 0:
        logger.warning("No any task messages were found at the queue '%s'.",
                       sqs_queue.q.name)
        return  # the queue is empty
    try:
        # Get message from SQS
        message = sqs_queue.get(timeout, attributes)
    except IndexError as e:
        logger.warning("Failed to get message from queue. Maybe it's empty.")
        # This exception will most likely be triggered because you were
        #  grabbing off an empty queue
        return
    except Exception as e:
        logger.error("Failed to get message from queue. %s.", str(e))
        # Catch all other exceptions to prevent the whole thing from crashing
        # TODO : Consider testing that sqs_scrape is still live, and restart
        #  it if needed
        return
    try:
        message = json.loads(message)
        # add attributes data to message, like date when message was sent
        message['attributes'] = sqs_queue.get_attributes()
    except Exception as e:
        logger.error("Message was provided not in json format. %s.", str(e))
        return
    return message, sqs_queue  # we will need sqs_queue later


def test_read_msg_from_fs(queue_name):
    global task_number
    try:
        task_number
    except NameError:
        task_number = -1
    task_number += 1
    fake_class = SQS_Queue(queue_name)
    with open('/tmp/%s' % queue_name, 'r') as fh:
        cur_line = 0
        while cur_line < task_number:
            fh.readline()
            cur_line += 1
        try:
            return json.loads(fh.readline()), fake_class
        except ValueError:
            return None


def set_global_variables_from_data_file():
    try:
        json_data = load_data_from_hash_datestamp_data()
        global RANDOM_HASH, DATESTAMP, FOLDERS_PATH
        RANDOM_HASH = json_data['random_hash']
        DATESTAMP = json_data['datestamp']
        FOLDERS_PATH = json_data['folders_path']
    except:
        logger.error("Required hash_datestamp_data wasn't created."
                     "Create it now.")
        generate_hash_datestamp_data()
        set_global_variables_from_data_file()


def _create_sqs_queue(queue_or_connection, queue_name, visib_timeout=30):
    if isinstance(queue_or_connection, SQS_Queue):
        queue_or_connection = queue_or_connection.conn
    queue_or_connection.create_queue(queue_name, visib_timeout)


def _get_server_ip():
    ip_fname = '/tmp/_server_ip'
    if os.path.exists(ip_fname):
        with open(ip_fname) as fh:
            return fh.read().strip()


def generate_msg(metadata, progress):
    _msg = {
        '_msg_id': metadata.get('task_id', metadata.get('task', None)),
        'utc_datetime': datetime.datetime.utcnow(),
        'progress': progress,
        'server_ip': _get_server_ip(),
        'searchterms_str': metadata.get('searchterms_str', None),
        'site': metadata.get('site', None),
        'server_name': metadata.get('server_name', None),
        'url': metadata.get('url', None),
        'urls': metadata.get('urls', None),
        'statistics': statistics.report_statistics()
    }
    return _msg


def json_serializer(obj):
    """ JSON serializer for objects not serializable by default json code """
    if isinstance(obj, (datetime.datetime, datetime.date)):
        serial = obj.isoformat()
        return serial


def write_msg_to_sqs(queue_name_or_instance, msg):
    try:
        if not isinstance(msg, (str, unicode)):
            msg = json.dumps(msg, default=json_serializer)
        if isinstance(queue_name_or_instance, (str, unicode)):
            sqs_queue = SQS_Queue(queue_name_or_instance)
        else:
            sqs_queue = queue_name_or_instance
        if getattr(sqs_queue, 'q', '') is None:
            logger.warning("Queue '%s' does not exist. Will be created new one.",
                           queue_name_or_instance)
            _create_sqs_queue(sqs_queue.conn, queue_name_or_instance)
            sqs_queue = SQS_Queue(queue_name_or_instance)
        time.sleep(5)  # let the queue get up
        sqs_queue.put(msg)
    except Exception as e:
        logger.error("Failed to put message to queue %s:\n%s",
                     queue_name_or_instance, str(e))


def test_write_msg_to_fs(queue_name_or_instance, msg):
    print 'Simulate msg to sqs: %s' % msg
    return

def put_msg_to_sqs(queue_name_or_instance, msg):
    if TEST_MODE:
        test_write_msg_to_fs(queue_name_or_instance, msg)
    else:
        write_msg_to_sqs(queue_name_or_instance, msg)


def compress_multiple_files(output_fname, filenames):
    """ Creates a single ZIP archive with the given files in it """
    try:
        import zlib
        mode = zipfile.ZIP_DEFLATED
    except ImportError:
        mode = zipfile.ZIP_STORED
    try:
        zf = zipfile.ZipFile(output_fname, 'a', mode, allowZip64=True)
        for filename in filenames:
            zf.write(filename=filename, arcname=os.path.basename(filename))
    except Exception as e:
        logger.error('Error trying to zip multiple log files: {}'.format(e))
    else:
        zf.close()


def put_file_into_s3(bucket_name, fname, compress=True,
                     is_add_file_time=False):
    if TEST_MODE:
        print 'Simulate put file to s3, %s' % fname
        return True

    if not os.path.exists(fname):
        logger.warning('File to upload doesnt exits: %r, aborting.', fname)
        return
    global S3_CONN, S3_BUCKET
    # Cut out file name
    filename = os.path.basename(fname)
    if compress:
        try:
            import zlib
            mode = zipfile.ZIP_DEFLATED
        except ImportError:
            mode = zipfile.ZIP_STORED
        archive_name = filename + '.zip'
        archive_path = fname + '.zip'
        zf = zipfile.ZipFile(archive_path, 'w', mode, allowZip64=True)
        try:
            zf.write(filename=fname, arcname=filename)
            logger.info("Adding %s to archive", filename)
        except Exception as ex:
            logger.error('Zipping Error')
            logger.exception(ex)
        finally:
            zf.close()

        filename = archive_name
        fname = archive_path
        # folders = ("/" + datetime.datetime.utcnow().strftime('%Y/%m/%d')
        #            + "/" + archive_name)

    # Generate file path for S3
    # folders = ("/" + datetime.datetime.utcnow().strftime('%Y/%m/%d')
    #            + "/" + filename)
    global FOLDERS_PATH
    folders = (FOLDERS_PATH + filename)
    logger.info("Uploading %s to Amazon S3 bucket %s", filename, bucket_name)
    try:
        k = Key(S3_BUCKET)
        # Set path to file on S3
        k.key = folders
        # Add file creation time to metadata
        if is_add_file_time:
            k.set_metadata('creation_time', get_file_cm_time(fname))
        # Upload file to S3
        k.set_contents_from_filename(fname)
        # Download file from S3
        # k.get_contents_to_filename('bar.csv')
        # key will be used to provide path at S3 for UI side
        return k
    except Exception:
        logger.warning("Failed to load files to S3. "
                       "Check file path and amazon keys/permissions.")


def dump_result_data_into_sqs(data_key, logs_key, csv_data_key,
                              queue_name, metadata):
    if TEST_MODE:
        print 'Simulate dump data into sqs'
        return
    global RANDOM_HASH, DATESTAMP, FOLDERS_PATH
    instance_log_filename = DATESTAMP + '____' + RANDOM_HASH + '____' + \
                            'remote_instance_starter2.log'
    s3_key_instance_starter_logs = (FOLDERS_PATH + instance_log_filename)
    msg = {
        '_msg_id': metadata.get('task_id', metadata.get('task', None)),
        'type': 'ranking_spiders',
        's3_key_data': data_key.key,
        's3_key_logs': logs_key.key,
        'bucket_name': data_key.bucket.name,
        'utc_datetime': datetime.datetime.utcnow(),
        's3_key_instance_starter_logs': s3_key_instance_starter_logs,
        'server_ip': _get_server_ip()
    }
    if csv_data_key:
        msg['csv_data_key'] = csv_data_key.key
    logger.info("Provide result msg %s to queue '%s'", msg, queue_name)
    if TEST_MODE:
        test_write_msg_to_fs(queue_name, msg)
    else:
        write_msg_to_sqs(queue_name, msg)


def dump_cached_data_into_sqs(cached_key, queue_name, metadata):
    instance_log_filename = DATESTAMP + '____' + RANDOM_HASH + '____' + \
                            'remote_instance_starter2.log'
    s3_key_instance_starter_logs = (FOLDERS_PATH + instance_log_filename)
    msg = {
        '_msg_id': metadata.get('task_id', metadata.get('task', None)),
        'type': 'ranking_spiders',
        's3_key_data': cached_key + '.jl.zip',
        's3_key_logs': cached_key + '.log.zip',
        'bucket_name': AMAZON_BUCKET_NAME,
        'utc_datetime': datetime.datetime.utcnow(),
        's3_key_instance_starter_logs': s3_key_instance_starter_logs,
        'server_ip': _get_server_ip()
    }
    if CONVERT_TO_CSV:
        msg['csv_data_key'] = cached_key + '.csv.zip'
    logger.info('Sending cached response to queue %s: %s', queue_name, msg)
    if TEST_MODE:
        test_write_msg_to_fs(queue_name, msg)
    else:
        write_msg_to_sqs(queue_name, msg)


def datetime_difference(d1, d2):
    """helper func to get difference between two dates in seconds"""
    res = d1 - d2
    return 86400 * res.days + res.seconds


def install_geckodriver(
        fallback_url='/mozilla/geckodriver/releases/download/v0.11.1/geckodriver-v0.11.1-linux64.tar.gz',
        github_latest_url='https://github.com/mozilla/geckodriver/releases/latest'):
    import lxml.html
    import requests
    logger.info('Installing geckodriver')

    response = requests.get(github_latest_url)

    try:
        link = lxml.html.fromstring(response.text).xpath(
            '//a[contains(@href, ".tar.gz")][contains(@href, "linux64")]/@href')[0]
    except IndexError:
        print('error while downloading latest geckodriver')
        link = fallback_url

    if link.startswith('/'):
        link = urlparse.urljoin('https://github.com', link)

    os.system('wget "%s" -O _geckodriver.tar.gz' % link)
    os.system('tar xf _geckodriver.tar.gz')
    os.system('mv geckodriver /home/spiders/')
    os.system('chmod +x /home/spiders/geckodriver')
    logger.info('Geckodriver installation finished')


class ScrapyTask(object):
    """
    class to control flow of the scrapy process with given task from SQS
    if task wasn't finished in allowed time, it will terminate
    """

    def __init__(self, queue, task_data, listener):
        """
        :param queue: SQS queue instance
        :param task_data: message with task data, taken from the queue
        :param listener: multiprocessing listener to establish connection
                         with the scrapy process
        """
        self.queue = queue
        self.task_data = task_data
        self.listener = listener  # common listener to accept connections
        self.process = None  # instance of Popen for scrapy
        self.process_bsr = None  # process for best seller ranking
        self.conn = None  # individual connection for each task
        self.return_code = None  # result of scrapy run
        self.finished = False  # is task finished
        self.finished_ok = False  # is task finished good
        self._stop_signal = False  # to break loop if needed
        self.start_date = None
        self.finish_date = None
        self.required_signals = self._parse_signal_settings(REQUIRED_SIGNALS)
        self._add_extensions()
        # self.extension_signals=self._parse_signal_settings(EXTENSION_SIGNALS)
        self.extension_signals = []
        self.current_signal = None  # tuple of key, value for current signal
        self.required_signals_done = OrderedDict()
        self.require_signal_failed = None  # signal, where failed
        self.items_scraped = 0
        self.spider_errors = 0

    def is_valid(self):
        scraper_name_validator_re = r"^[A-Za-z0-9_]*$"
        if not re.match(scraper_name_validator_re, self.task_data["site"].strip()):
            return False
        return True

    def get_unique_name(self):
        # convert task data into unique name
        global RANDOM_HASH, DATESTAMP
        searchterms_str = self.task_data.get('searchterms_str', None)
        site = self.task_data['site'].strip()
        if isinstance(searchterms_str, (str, unicode)):
            try:
                searchterms_str = searchterms_str.decode('utf8')
            except UnicodeEncodeError:  # special chars may break
                pass
        server_name = self.task_data['server_name']
        server_name = slugify(server_name)
        job_name = DATESTAMP + '____' + RANDOM_HASH + '____' + server_name + '--'
        task_id = self.task_data.get('task_id',
                                     self.task_data.get('task', None))
        if task_id:
            job_name += str(task_id)
        if searchterms_str:
            additional_part = unidecode.unidecode(
                searchterms_str.replace("'", '')).replace(
                ' ', '-').replace('/', '').replace('\\', '').replace('%', '').replace('$', '')
        else:
            # maybe should be changed to product_url
            additional_part = 'single-product-url-request'
        job_name += '____' + additional_part + '____' + site
        job_name = sub("\(|\)|&|;|'", "", job_name)
        # truncate resulting string as file name limitation is 256 characters
        return job_name[:200]

    def _parse_signal_settings(self, signal_settings):
        """
        calculate running time for the scrapy process
        based on the signals settings
        """
        d = OrderedDict()
        wait = 'wait'
        # dict with signal name as key and dict as value
        for s in signal_settings:
            d[s[0]] = {wait: s[1], STATUS_STARTED: None, STATUS_FINISHED: None}
        return d

    def _add_extensions(self):
        """
        add time limit to run scrapy process, based on the parameters of task
        currently supports cache downloading/uploading
        """
        ext_cache_down = 'cache_downloading'
        ext_cache_up = 'cache_uploading'
        cmd_args = self.task_data.get('cmd_args', {})
        if not isinstance(cmd_args, dict):
            cmd_args = {}
        if cmd_args.get('save_raw_pages', False):
            self.required_signals[SIGNAL_SPIDER_OPENED]['wait'] += \
                EXTENSION_SIGNALS[ext_cache_up]
        if cmd_args.get('load_raw_pages'):
            self.required_signals[SIGNAL_SCRIPT_CLOSED]['wait'] += \
                EXTENSION_SIGNALS[ext_cache_down]

    def get_total_wait_time(self):
        """
        get max wait time for scrapy process in seconds
        """
        s = sum([r['wait'] for r in self.required_signals.itervalues()])
        if self.current_signal:
            s += self.current_signal[1]['wait']

        return s

    def _dispose(self):
        """
        used to terminate scrapy process, called from finish method
        kill process if running, drop connection if opened
        """

        if self.process_bsr and self.process_bsr.poll() is None:
            try:
                os.killpg(os.getpgid(self.process_bsr.pid), 9)
            except OSError as e:
                logger.error('OSError: %s', e)
        if self.process and self.process.poll() is None:
            logger.info('Trying to dispose process: {}'.format(self.process.pid))
            try:
                os.killpg(os.getpgid(self.process.pid), 9)
            except OSError as e:
                logger.error('OSError: %s', e)
        if self.conn:
            self.conn.close()

    def _get_next_signal(self, date_time):
        """get and remove next signal from the main queue"""
        logger.warning('_get_next_signal called')
        try:
            k = self.required_signals.iterkeys().next()
        except StopIteration:
            return None
        v = self.required_signals.pop(k)
        v[STATUS_STARTED] = date_time
        return k, v

    def _get_signal_by_data(self, data):
        """
        return current main signal or
        one of the extension signals, for which data is sent,
        depending on the data, received from the scrapy process
        """
        if data['name'] == 'item_scraped':
            self.items_scraped += 1
            return None
        elif data['name'] == 'item_dropped':
            # items dropped - most likely because of "subitems" mode,
            # so calculate the number of really scraped items
            if random.randint(0, 30) == 0:  # do not overload server's filesystem
                self._update_items_scraped()
            return
        elif data['name'] == 'spider_error':
            self.spider_errors += 1
            return None
        is_ext = False
        if self.current_signal and self.current_signal[0] == data['name']:
            signal = self.current_signal
        else:
            is_ext = True
            signal = (data['name'], self.extension_signals.get(data['name']))
        return is_ext, signal

    def _process_signal_data(self, signal, data, date_time, is_ext):
        """
        set signal as finished, collect its duration
        """
        new_status = data['status']  # opened/closed
        if signal[1][new_status]:  # if value is already set
            res = False
        else:
            res = True
        self._signal_succeeded(signal, date_time, is_ext)
        return res

    def _signal_failed(self, signal, date_time, ex):
        """
        set signal as failed, when it takes more then allowed time
        :param signal: signal itself
        :param date_time: when signal failed
        :param ex: exception that caused fail, derived from the FlowError
        """
        signal[1]['failed'] = True
        signal[1][STATUS_FINISHED] = date_time
        signal[1]['reason'] = ex.__class__.__name__

        logger.error('Task #%s failed. %s',
                     self.task_data.get('task_id', 0), signal)

        self.require_signal_failed = signal
        self.send_current_status_to_sqs('failed')

    def _signal_succeeded(self, signal, date_time, is_ext):
        """set finish time for signal and save in finished signals if needed"""
        signal[1][STATUS_FINISHED] = date_time
        if not is_ext:
            self.required_signals_done[signal[0]] = signal[1]

    def _get_daemon_logs_files(self):
        """ Returns logs from the /tmp/ dir """
        for fname in os.listdir('/tmp/'):
            fname = os.path.join('/tmp/', fname)
            if fname.lower().endswith('.log'):
                yield fname

    def _zip_daemon_logs(self, output_fname='/tmp/daemon_logs.zip'):
        """
        zips all log giles, found in the /tmp dir to the output_fname
        """
        log_files = list(self._get_daemon_logs_files())
        logger.info('Trying to zip all daemon log files, got log_files: {}'.format(log_files))
        if os.path.exists(output_fname):
            os.unlink(output_fname)
        compress_multiple_files(output_fname, log_files)
        return output_fname

    @staticmethod
    def _wait_for_screenshot_job_to_finish(output_path):
        logger.warning('Screenshot output file does not exist, or is empty, waiting 120 seconds')
        for x in xrange(12):  # wait max 120 seconds
            time.sleep(10)
            if os.path.exists(output_path + '.screenshot.jl'):
                # check file size because empty files seem to get created immediately
                if os.path.getsize(output_path + '.screenshot.jl') > 10:
                    return True
        logger.error('Screenshot output file does not exist, or is empty, giving up: %s' % (
            output_path + '.screenshot.jl'))
        return False

    def _finish(self):
        """
        called after scrapy process finished, or failed for some reason
        sends logs and data files to amazon
        """
        self._stop_signal = True
        self._dispose()

        output_path = self.get_output_path()
        if self.process_bsr and self.finished_ok:
            logger.info('Collecting best sellers data...')
            temp_file = output_path + 'temp_file.jl'
            cmd = '%s/product-ranking/add-best-seller.py %s %s > %s' % (
                REPO_BASE_PATH, output_path + '.jl',
                output_path + '_bs.jl', temp_file)
            try:  # if best seller failed, download data without bsr column
                output = check_output(cmd, shell=True, stderr=STDOUT)
                logger.info('BSR script output: %s', output)
                with open(temp_file) as bs_file:
                    lines = bs_file.readlines()
                    with open(output_path + '.jl', 'w') as main_file:
                        main_file.writelines(lines)
                os.remove(temp_file)
            except CalledProcessError as ex:
                logger.error('Best seller conversion error')
                logger.error(ex.output)
                logger.exception(ex)
        try:
            data_key = put_file_into_s3(
                AMAZON_BUCKET_NAME, output_path + '.jl')
        except Exception as ex:
            logger.error('Data file uploading error')
            logger.exception(ex)
            data_key = None
        logs_key = put_file_into_s3(
            AMAZON_BUCKET_NAME, output_path + '.log')

        if self.is_screenshot_job():
            jl_results_path = output_path + '.screenshot.jl'
            url2screenshot_log_path = output_path + '.screenshot.log'
            screenshot_finished = self._wait_for_screenshot_job_to_finish(output_path=output_path)
            if not screenshot_finished:
                logger.info('Screenshot job isnt finished, nothing to upload')
            else:
                try:
                    put_file_into_s3(
                        AMAZON_BUCKET_NAME, jl_results_path,
                        is_add_file_time=True)
                except Exception as ex:
                    logger.error('Screenshot file uploading error')
                    logger.exception(ex)
                try:
                    put_file_into_s3(
                        AMAZON_BUCKET_NAME, url2screenshot_log_path,
                        is_add_file_time=True)
                except Exception as ex:
                    logger.error('url2screenshot log file uploading error')
                    logger.exception(ex)

        csv_data_key = None
        global CONVERT_TO_CSV
        if CONVERT_TO_CSV:
            try:
                csv_filepath = convert_json_to_csv(output_path, logger)
                logger.info('JSON converted to CSV file created at: %r.', csv_filepath)
                csv_data_key = put_file_into_s3(
                    AMAZON_BUCKET_NAME, csv_filepath)
            except Exception as e:
                logger.warning(
                    "CSV converter failed with exception: %s", str(e))

        if data_key and logs_key:
            dump_result_data_into_sqs(
                data_key, logs_key, csv_data_key,
                self.task_data['server_name'] + OUTPUT_QUEUE_NAME, self.task_data)
        else:
            logger.error("Failed to load info to results sqs. Amazon keys "
                         "wasn't received. data_key=%r, logs_key=%r.",
                         data_key, logs_key)

        # Disabled for now, need to refactor this into something meaningful
        # TODO Rework spider output
        # logger.info("Spider default output:\n%s",
        #             self.process.stdout.read().strip())
        logger.info('Finish task #%s.', self.task_data.get('task_id', 0))

        self.finished = True
        self.finish_date = datetime.datetime.utcnow()
        self.task_data['finish_time'] = \
            time.mktime(self.finish_date.timetuple())

    def _update_items_scraped(self):
        output_path = self.get_output_path() + '.jl'
        if os.path.exists(output_path):
            cont = None
            try:
                with open(output_path, 'r') as fh:
                    cont = fh.readlines()
            except Exception as ex:
                logger.error('Could not read output file [%s]: %s' % (output_path, str(ex)))
            if cont is not None:
                if isinstance(cont, (list, tuple)):
                    self.items_scraped = len(cont)

    def _success_finish(self):
        """
        used to indicate, that scrapy process finished
        successfully in allowed time
        """
        # run this task after scrapy process successfully finished
        # cache result, if there is at least one scraped item
        time.sleep(2)  # let the data to be dumped into the output file?
        self._update_items_scraped()
        if self.items_scraped:
            self.save_cached_result()
        else:
            logger.warning('Not caching result for task %s (%s) '
                           'due to no scraped items.',
                           self.task_data.get('task_id'),
                           self.task_data.get('server_name'))
        logger.info('Success finish task #%s', self.task_data.get('task_id', 0))
        self.finished_ok = True

    def get_output_path(self):
        """
        get abs path, where to store logs and data files for scrapy task
        """
        output_path = '%s/%s' % (
            os.path.expanduser(JOB_OUTPUT_PATH), self.get_unique_name())
        return output_path

    def _parse_task_and_get_cmd(self, is_bsr=False):
        """
        convert data of the SQS task to the scrapy run command with
        all parameters which are given in task data
        """
        searchterms_str = self.task_data.get('searchterms_str', None)
        url = self.task_data.get('url', None)
        urls = self.task_data.get('urls', None)
        site = self.task_data['site'].strip()
        cmd_line_args = self.task_data.get('cmd_args', {})
        if not isinstance(cmd_line_args, dict):
            cmd_line_args = {}
        output_path = self.get_output_path()
        options = ' '
        arg_name = arg_value = None
        for key, value in cmd_line_args.items():
            # exclude raw s3 cache - otherwise 2 spiders will work in parallel
            #  with cache enabled
            if is_bsr and key == 'save_raw_pages':
                continue
            options += ' -a {}="{}"'.format(key, value)
        if searchterms_str:
            arg_name = 'searchterms_str'
            arg_value = searchterms_str.replace('"', '\\"').replace('$', '\\$')
        if url:
            arg_name = 'product_url'
            arg_value = url
        if urls:
            arg_name = 'products_url'
            arg_value = urls
        spider_name = site+'_products'
        if not is_bsr:
            cmd = ('cd %s/product-ranking'
                   ' && scrapy crawl %s -a %s="%s" %s'
                   ' -s LOG_FILE=%s -s WITH_SIGNALS=1 -o %s &') % (
                REPO_BASE_PATH, spider_name, arg_name, arg_value,
                options, output_path+'.log', output_path+'.jl'
            )
        else:
            cmd = ('cd %s/product-ranking'
                   ' && scrapy crawl %s -a %s="%s" %s'
                   ' -a search_sort=%s -s LOG_FILE=%s -o %s &') % (
                REPO_BASE_PATH, spider_name, arg_name, arg_value,
                options, "best_sellers", output_path+'_bs.log',
                output_path+'_bs.jl')
        # Override aerospike settings for high-frequency price scraping
        if cmd_line_args.get("summary"):
            logger.debug('Aerospike turned OFF, summary task {}'.format(cmd))
            return cmd
        if TEST_MODE:
            return cmd
        branchname = self.task_data.get("branch_name", "sc_production")
        key_name = "cache.json"
        # New url based Aerospike cache
        logger.debug('Branch name is {}, aerospike config file name is {}'.format(branchname, key_name))
        raw_settings = spiders_shared_code.utils.get_raw_settings(key_name=key_name)
        logger.debug('Got Aerospike cache settings from bucket: {}'.format(raw_settings))
        if branchname == "sc_production":
            aerospike_cache_settings = raw_settings.get("production")
        else:
            aerospike_cache_settings = raw_settings.get("dev")
        # Legacy cache format
        # settings = spiders_shared_code.utils.compile_settings(raw_settings, domain=netloc)
        if aerospike_cache_settings is None:
            return cmd
        elif spider_name not in aerospike_cache_settings.get('include', []):
            return cmd
        table = spider_name.split("_")[0]
        max_age = aerospike_cache_settings.get('max-age', aerospike_cache_settings.get('cache_ttl', False))
        CACHE = {
            'MAXAGE': max_age,
            'HOST': aerospike_cache_settings.get('host'),
            'PORT': aerospike_cache_settings.get('port'),
            'TABLE': table,
            'NAMESPACE': aerospike_cache_settings.get('namespace', 'cache')
        }
        logger.debug('Aerospike resulting config {}'.format(pprint.pformat(CACHE)))

        if all(CACHE.values()):
            cmd = cmd[:-1]  # remove &
            cmd += ' -s AEROSPIKECACHE_ENABLED=1 '\
                '-s AEROSPIKECACHE_HOST={HOST} '\
                '-s AEROSPIKECACHE_PORT={PORT} '\
                '-s AEROSPIKECACHE_TABLE={TABLE} '\
                '-s AEROSPIKECACHE_NAMESPACE={NAMESPACE} '\
                '-s AEROSPIKECACHE_MAXAGE={MAXAGE} '\
                .format(**CACHE)
            cmd += ' &'
            logger.debug('Aerospike turned ON, cmd {}'.format(cmd))
        else:
            logger.debug('Aerospike cache turned OFF, cmd {}'.format(cmd))

        return cmd

    def _start_scrapy_process(self):
        """
        starts scrapy process for current SQS task
        also starts second process for best_sellers if required
        """
        cmd = self._parse_task_and_get_cmd()
        self.process = Popen(cmd, shell=True, stdout=PIPE,
                             stderr=PIPE, preexec_fn=os.setsid)
        if self.task_data.get('with_best_seller_ranking', False):
            logger.info('With best seller ranking')
            cmd = self._parse_task_and_get_cmd(True)
            self.process_bsr = Popen(cmd, shell=True, stdout=PIPE,
                                     stderr=PIPE, preexec_fn=os.setsid)
        else:
            logger.info('Skipping best seller')
        logger.info('Scrapy process started for task #%s',
                    self.task_data.get('task_id', 0))

    def _establish_connection(self):
        """
        tries to accept connection from the scrapy process to receive
        stats on signals, like spider_error, spider_opened etc
        """
        self.conn = self.listener.accept()

    def _dummy_client(self):
        """used to interrupt waiting for the connection from scrapy process
        with connecting by itself, closes connection immediately"""
        logger.warning('Running dummy client for task #%s',
                       self.task_data.get('task_id', 0))
        Client(LISTENER_ADDRESS).close()

    def _try_connect(self, wait):
        """
        tries to establish connection to scrapy process in the given time
        checks status of connection each second
        if no connection was done in the given time, simulate it and close
        :param wait: time in seconds to wait
        :return: success of connection
        """
        t = Thread(target=self._establish_connection)
        counter = 0
        t.start()
        while not self._stop_signal and counter < wait:
            time.sleep(1)
            counter += 1
            if self.conn:  # connected successfully
                return True
        # if connection failed
        self._dummy_client()
        if self.conn:
            self.conn.close()
            self.conn = None
        return False

    def _try_finish(self, wait):
        """
        runs as last signal, checks if process finished and  has return code
        """
        counter = 0
        while not self._stop_signal and counter < wait:
            time.sleep(1)
            counter += 1
            res = self.process.poll()
            res_bsr = self.process_bsr.poll() if self.process_bsr else True
            if res is not None and res_bsr is not None:
                logger.info('Finish try succeeded')
                self.return_code = res
                time.sleep(15)
                return True
        else:
            logger.warning('Killing scrapy process manually, task id is %s',
                           self.task_data.get('task_id', 0))
        # kill process group, if not finished in allowed time
        if self.process_bsr:
            try:
                self.process_bsr.terminate()
            except OSError as e:
                logger.error('Kill process bsr error in task #%s: %s',
                             self.task_data.get('task_id', 0), e)
        try:
            self.process.terminate()
        except OSError as e:
            logger.error('Kill process error in task #%s: %s',
                         self.task_data.get('task_id', 0), e)
        return False

    def _run_signal(self, next_signal, step_time_start):
        """
        controls the flow of running given signal to scrapy process
        """
        max_step_time = next_signal[1]['wait']
        if next_signal[0] == SIGNAL_SCRIPT_OPENED:  # first signal
            res = self._try_connect(max_step_time)
            if not res:
                raise ConnectError
            self._signal_succeeded(next_signal,
                                   datetime.datetime.utcnow(), False)
            self.send_current_status_to_sqs(0)
            return True
        elif next_signal[0] == SIGNAL_SCRIPT_CLOSED:  # last signal
            res = self._try_finish(max_step_time)
            if not res:
                raise FinishError
            self._signal_succeeded(next_signal,
                                   datetime.datetime.utcnow(), False)
            self.send_current_status_to_sqs('finished')
            return True
        step_time_passed = 0
        while not self._stop_signal and step_time_passed < max_step_time:
            has_data = self.conn.poll(max_step_time - step_time_passed)
            sub_step_time = datetime.datetime.utcnow()
            step_time_passed = datetime_difference(sub_step_time,
                                                   step_time_start)
            if has_data:
                try:
                    data = self.conn.recv()
                except EOFError as ex:
                    logger.error('eof error: %s', ex)
                    self._signal_failed(next_signal,
                                        datetime.datetime.utcnow(), False)
                    self._finish()
                    return
                s_d = self._get_signal_by_data(data)
                if not s_d:  # item_scraped or spider_error signals
                    continue
                is_ext, signal = s_d
                res = self._process_signal_data(signal, data,
                                                sub_step_time, is_ext)
                if not res:
                    raise SignalSentTwiceError
                if not is_ext:
                    return True
        else:
            raise SignalTimeoutError

    def _listen(self):
        """
        checks signal to finish in allowed time, otherwise raises error
        and stops scrapy process, logs duration for given signal
        """
        while not self._stop_signal:  # run through all signals
            logger.warning('checking signal')
            step_time_start = datetime.datetime.utcnow()
            next_signal = self._get_next_signal(step_time_start)
            if not next_signal:
                # all steps are finished
                self._success_finish()
                break
            self.current_signal = next_signal
            try:
                self._run_signal(next_signal, step_time_start)
            except FlowError as ex:
                self._signal_failed(next_signal, datetime.datetime.utcnow(), ex)
                break
        self.finish_date = datetime.datetime.utcnow()
        self._finish()

    def start(self):
        """
        start scrapy process, try to establish connection with it,
        terminate if fails
        """
        # it may break during task parsing, for example wrong server name or
        # unsupported characters in the name os spider
        try:
            start_time = datetime.datetime.utcnow()
            self.start_date = start_time
            self.task_data['start_time'] = \
                time.mktime(self.start_date.timetuple())
            self._start_scrapy_process()
            first_signal = self._get_next_signal(start_time)
        except Exception as ex:
            logger.warning('Error occurred while starting scrapy: %s', ex)
            return False
        try:
            self._run_signal(first_signal, start_time)
            return True
        except FlowError as ex:
            self._signal_failed(first_signal, datetime.datetime.utcnow(), ex)
            self._finish()
            return False

    def run(self):
        """
        run listening of scrapy process execution in separate thread
        to not block main thread and allow multiple tasks running same time
        """
        t = Thread(target=self._listen)
        t.start()

    def stop(self):
        """send stop signal, doesn't guaranties to stop immediately"""
        self._stop_signal = True

    def is_finished(self):
        return self.finished

    def is_finised_ok(self):
        return self.finished_ok

    def get_cached_result(self, queue_name):
        res = get_task_result_from_cache(self.task_data, queue_name)
        if res:
            self.send_current_status_to_sqs('finished')
            dump_cached_data_into_sqs(
                res, self.task_data['server_name'] + OUTPUT_QUEUE_NAME,
                self.task_data)
        return bool(res)

    def save_cached_result(self):
        return save_task_result_to_cache(self.task_data, self.get_output_path())

    def is_screenshot_job(self):
        cmd_args = self.task_data.get('cmd_args', {})
        # leave "make_screenshot_for_url" for backward compatibility
        return cmd_args.get('make_screenshot_for_url', cmd_args.get('make_screenshot', False))

    def start_screenshot_job_if_needed(self):
        """ Starts a new url2screenshot local job, if needed """
        url2scrape = None
        if self.task_data.get('product_url', self.task_data.get('url', None)):
            url2scrape = self.task_data.get('product_url', self.task_data.get('url', None))
        # TODO: searchterm jobs? checkout scrapers?
        if url2scrape:
            # scrapy_path = "/home/spiders/virtual_environment/bin/scrapy"
            # python_path = "/home/spiders/virtual_environment/bin/python"
            output_path = self.get_output_path()
            cmd = ('cd {repo_base_path}/product-ranking'
                   ' && scrapy crawl url2screenshot_products'
                   ' -a product_url="{url2scrape}" '
                   ' -a width=1280 -a height=1024 -a timeout=90 '
                   ' -s LOG_FILE="{log_file}"'
                   ' -o "{output_file}" &').format(
                repo_base_path=REPO_BASE_PATH,
                log_file=output_path + '.screenshot.log', url2scrape=url2scrape,
                output_file=output_path + '.screenshot.jl')
            logger.info('Starting a new parallel screenshot job: %s' % cmd)
            os.system(cmd)  # use Popen instead?

    def report(self):
        """returns string with the task running stats"""
        s = 'Parsed task #%s, command %r.\n' % (self.task_data.get('task_id', 0),
                                                self._parse_task_and_get_cmd())
        if self.start_date:
            s += 'Task started at %s.\n' % str(self.start_date.time())
        if self.finish_date:
            s += 'Finished %s at %s, duration %s.\n' % (
                'successfully' if self.finished_ok else 'containing errors',
                str(self.finish_date.time()),
                str(self.finish_date - self.start_date))
        if self.require_signal_failed:
            sig = self.require_signal_failed
            s += 'Failed signal is: %r, reason %r, started at %s, ' \
                 'finished at %s, duration %s.\n' % (
                     sig[0], sig[1]['reason'],
                     str(sig[1][STATUS_STARTED].time()),
                     str(sig[1][STATUS_FINISHED].time()),
                     str(sig[1][STATUS_FINISHED] - sig[1][STATUS_STARTED]))
        s += 'Items scrapped: %s, spider errors: %s.\n' % (
            self.items_scraped, self.spider_errors)
        if self.required_signals_done:
            s += 'Succeeded required signals:\n'
            for sig in self.required_signals_done.iteritems():
                s += '\t%r, started at %s, finished at %s, duration %s;\n' % (
                    sig[0], str(sig[1][STATUS_STARTED].time()),
                    str(sig[1][STATUS_FINISHED].time()),
                    str(sig[1][STATUS_FINISHED] - sig[1][STATUS_STARTED]))
        else:
            s += 'None of the signals are finished.\n'
        return s

    def send_current_status_to_sqs(self, status=None):
        msg = generate_msg(
            self.task_data, status if status else self.items_scraped)
        put_msg_to_sqs(
            self.task_data['server_name'] + PROGRESS_QUEUE_NAME, msg)
        # put current progress to S3 as well, for easier debugging & tracking
        progress_fname = self.get_output_path() + '.progress'
        with open(progress_fname, 'w') as fh:
            fh.write(json.dumps(msg, default=json_serializer))
        put_file_into_s3(AMAZON_BUCKET_NAME, progress_fname)


def get_file_cm_time(file_path):
    """Get unix timestamp of create date of file or last modify date."""
    try:
        create_time = os.path.getctime(file_path)
        if create_time:
            return int(create_time)
        modify_time = os.path.getmtime(file_path)
        if modify_time:
            return int(modify_time)
    except (OSError, ValueError) as e:
        logger.error('Error while get creation time of file. ERROR: %s.',
                     str(e))
    return 0


def get_task_result_from_cache(task, queue_name):
    """try to get cached result for some task"""
    task_id = task.get('task_id', 0)
    server = task.get('server_name', '')
    if task.get(CACHE_GET_IGNORE_KEY, False) or server == 'test_server':
        logger.info('Ignoring cache result for task %s (%s).', task_id, server)
        return None
    url = CACHE_HOST + CACHE_URL_GET
    data = dict(task=json.dumps(task), queue=queue_name)
    try:
        resp = requests.post(url, data=data, timeout=CACHE_TIMEOUT,
                             auth=CACHE_AUTH)
    except Exception as ex:
        logger.warning(ex)
        return None
    if resp.status_code != 200:  # means no cached data was received
        logger.info('No cached result for task %s (%s). '
                    'Status %s, message is: "%s".',
                    task_id, server, resp.status_code, resp.text)
        return None
    else:  # got task
        logger.info('Got cached result for task %s (%s): %s.',
                    task_id, server, resp.text)
        return resp.text


def save_task_result_to_cache(task, output_path):
    """save cached result for task to sqs cache"""
    task_id = task.get('task_id', 0)
    server = task.get('server_name', '')
    if task.get(CACHE_SAVE_IGNORE_KEY, False):
        logger.info('Ignoring save to cache for task %s (%s)', task_id, server)
        return False
    message = FOLDERS_PATH + os.path.basename(output_path)
    url = CACHE_HOST + CACHE_URL_SAVE
    data = dict(task=json.dumps(task), message=message)
    try:
        resp = requests.post(url, data=data, timeout=CACHE_TIMEOUT,
                             auth=CACHE_AUTH)
    except Exception as ex:  # timeout passed but no response received
        logger.warning(ex)
        return False
    if resp.status_code != 200:
        logger.warning('Failed to save cached result for task %s (%s). '
                       'Status %s, message: "%s".',
                       task_id, server, resp.status_code, resp.text)
        return False
    else:
        logger.info('Saved cached result for task %s (%s).', task_id, server)
        return True


def log_failed_task(task):
    """
    log broken task
    if this function returns True, task is considered
    as failed max allowed times and should be removed
    """
    url = CACHE_HOST + CACHE_URL_FAIL
    data = dict(task=json.dumps(task))
    try:
        resp = requests.post(url, data=data, timeout=CACHE_TIMEOUT,
                             auth=CACHE_AUTH)
    except Exception as ex:
        logger.warning(ex)
        return False
    if resp.status_code != 200:
        logger.warning('Mark task as failed wrong response status code: %s, %s',
                       resp.status_code, resp.text)
        return False
    # resp.text contains only 0 or 1 number,
    #  1 indicating that task should be removed
    try:
        return json.loads(resp.text)
    except ValueError as ex:
        logger.warning('JSON conversion error: %s', ex)
        return False


def notify_cache(task, is_from_cache=False):
    """send request to cache (for statistics)"""
    url = CACHE_HOST + CACHE_URL_STATS
    json_task = json.dumps(task)
    logger.info('notify_cache: sending request to cache for stats, task: %s', json_task)
    data = dict(task=json_task, is_from_cache=json.dumps(is_from_cache))
    if 'start_time' in task and task['start_time']:
        if ('finish_time' in task and not task['finish_time']) or \
                        'finish_time' not in task:
            task['finish_time'] = int(time.time())
    data = dict(task=json.dumps(task), is_from_cache=json.dumps(is_from_cache))
    try:
        resp = requests.post(url, data=data, timeout=CACHE_TIMEOUT,
                             auth=CACHE_AUTH)
        logger.info('notify_cache: updated task (%s), status %s.',
                    task.get('task_id'), resp.status_code)
    except Exception as ex:
        logger.warning('notify_cache: update completed task error: %s.', ex)


def del_duplicate_tasks(tasks):
    """Checks all tasks (its ids) and removes ones, which ids are repeating"""
    task_ids = []
    for i in xrange(len(tasks) - 1, -1, -1):  # iterate from the end
        t = tasks[i].task_data.get('task_id')
        if t is None:
            continue
        if t in task_ids:
            logger.warning('Found duplicate task for id %s, removing it.', t)
            del tasks[i]
            continue
        task_ids.append(t)


def is_task_taken(new_task, tasks):
    """
    check, if task with such id already taken
    """
    task_ids = [t.task_data.get('task_id') for t in tasks]
    new_task_id = new_task.get('task_id')
    if new_task_id is None:
        return False
    taken = new_task_id in task_ids
    if taken:
        logger.info('Task {} is already taken'.format(new_task_id))
    return taken


def store_tasks_metrics(task, redis_db):
    """This method will just increment required key in redis database
        if connection to the database exist."""
    if TEST_MODE:
        print 'Simulate redis incremet, key is %s' % JOBS_COUNTER_REDIS_KEY
        print 'Simulate redis incremet, key is %s' % JOBS_STATS_REDIS_KEY
        return
    if not redis_db:
        return
    try:
        # increment quantity of tasks spinned up during the day.
        redis_db.incr(JOBS_COUNTER_REDIS_KEY)
    except Exception as e:
        logger.warning("Failed to increment redis metric '%s' "
                       "with exception '%s'", JOBS_COUNTER_REDIS_KEY,
                       e)
    generated_key = '%s:%s:%s' % (
        task.get('server_name', 'UnknownServer'),
        task.get('site', 'UnknownSite'),
        ('term' if 'searchterms_str' in task and task['searchterms_str']
         else 'url')
    )
    try:
        redis_db.hincrby(JOBS_STATS_REDIS_KEY, generated_key, 1)
    except Exception as e:
        logger.warning("Failed to increment redis key '%s' and"
                       "redis metric '%s' with exception '%s'",
                       JOBS_STATS_REDIS_KEY, generated_key, e)


def get_instance_billing_limit_time():
    try:
        return int(global_settings_from_redis.get('instance_max_billing_time'))
    except Exception as e:
        logger.warning('Error while getting instance billing '
                       'time limit from redis cache. Limitation is disabled.'
                       ' ERROR: %s.', str(e))
    return 0


def shut_down_instance_if_swap_used():
    """ Shuts down the instance of swap file is used heavily
    :return:
    """
    stats = statistics.report_statistics()
    swap_usage_total = stats.get('swap_usage_total', None)
    ram_usage_total = stats.get('ram_usage_total', None)

    logger.info('Checking swap and RAM usage...')

    if swap_usage_total and ram_usage_total:
        try:
            swap_usage_total = float(ram_usage_total)
            ram_usage_total = float(ram_usage_total)
        except:
            logger.error('Swap and RAM usage check failed during float() conversion')
            return

        if ram_usage_total > 70:
            if swap_usage_total > 10:
                # we're swapping very badly!
                logger.error('Swap and RAM usage is too high! Terminating instance')
                try:
                    conn = boto.connect_ec2()
                    instance_id = get_instance_metadata()['instance-id']
                    conn.terminate_instances(instance_id)
                except Exception as e:
                    logger.error('Failed to terminate instance, exception: %s' % str(e))


def get_uptime():
    """
    Get instance billing time.
    """
    try:
        output = Popen('cat /proc/uptime', shell=True, stdout=PIPE, close_fds=True)
    except Exception as e:
        logging.warning('Error getting current uptime: {}'.format(e))
        return "123.0"
    else:
        return float(output.communicate()[0].split()[0])


def restart_scrapy_daemon():
    """
    Restart this script after update source code.
    """
    global REPO_BASE_PATH
    logger.info('Scrapy daemon restarting...')
    arguments = ['python'] + [REPO_BASE_PATH + '/deploy/sqs_ranking_spiders/scrapy_daemon.py'] + sys.argv[1:]
    if 'restarted' not in arguments:
        arguments += ['restarted']
    else:
        logger.error('Error while restarting scrapy daemon. '
                     'Already restarted.')
        return
    logging.info('Starting %s with args %s' % (sys.executable, arguments))
    os.execv(sys.executable, arguments)


def daemon_is_restarted():
    """
    Check this script is restarted copy or not.
    """
    return 'restarted' in sys.argv


def load_options_after_restart():
    """
    Load previous script options.
    """
    try:
        with open(OPTION_FILE_FOR_RESTART, 'r') as f:
            options = f.read()
            print '\n\n', options, '\n\n'
        os.remove(OPTION_FILE_FOR_RESTART)
        return json.loads(options)
    except Exception as e:
        logger.error('Error while load old options for scrapy daemon. '
                     'ERROR: %s' % str(e))
    return {}


def save_options_for_restart(options):
    """
    Save script options for another copy.
    """
    try:
        options = json.dumps(options)
        with open(OPTION_FILE_FOR_RESTART, 'w') as f:
            f.write(options)
    except Exception as e:
        logger.error('Error while save options for scrapy daemon. '
                     'ERROR: %s' % str(e))


def prepare_queue_after_restart(options):
    """
    Load queue and message from disk after restart.
    """
    if TEST_MODE:
        global task_number
        try:
            task_number
        except NameError:
            task_number = -1
        task_number += 1
        fake_class = SQS_Queue(options['queue']['name'])
        return options['task_data'], fake_class
    # Connection to SQS
    queue = SQS_Queue(
        name=options['queue']['queue_name'],
        region=options['queue']['conn_region']
    )
    # Create a new message
    queue.currentM = queue.q.message_class()
    # Fill message
    queue.currentM.body = options['queue']['body']
    queue.currentM.attributes = options['queue']['attributes']
    queue.currentM.md5_message_attributes = \
        options['queue']['md5_message_attributes']
    queue.currentM.message_attributes = options['queue']['message_attributes']
    queue.currentM.receipt_handle = options['queue']['receipt_handle']
    queue.currentM.id = options['queue']['id']
    queue.currentM.md5 = options['queue']['md5']
    return options['task_data'], queue


def store_queue_for_restart(queue):
    """
    Save queue options and message to disk for load after restart.
    """
    if TEST_MODE:
        return queue.__dict__
    if not queue.currentM:
        logger.error('Message was not found in queue for restart daemon.')
        return None
    return {
        'conn_region': queue.conn.region.name,
        'queue_name': queue.q.name,
        'body': queue.currentM.get_body(),
        'attributes': queue.currentM.attributes,
        'md5_message_attributes': queue.currentM.md5_message_attributes,
        'message_attributes': queue.currentM.message_attributes,
        'receipt_handle': queue.currentM.receipt_handle,
        'id': queue.currentM.id,
        'md5': queue.currentM.md5
    }

def get_and_save_branch_info(temp_filename):
    try:
        # run command to get branch name and build
        git_command = "git symbolic-ref --short HEAD && git log -1 --format=%cd"
        output = Popen(git_command, shell=True, stdout=PIPE, close_fds=True)
        branch_data = str(output.communicate()[0]).strip()
        with open(temp_filename, 'w') as tempfile:
            tempfile.write(branch_data)
        branch_list = branch_data.split("\n")
    except Exception:
        logger.error("Error saving branch info to {}".format(traceback.format_exc()))
        return None, None
    else:
        logger.info("Saved branch info {} to {}".format(branch_list, temp_filename))
        return branch_list


def main():
    LOG_HISTORY = LogHistory("scrapy_daemon")
    LOG_HISTORY.start_log()
    if not TEST_MODE:
        instance_meta = get_instance_metadata()
        inst_ip = instance_meta.get('public-ipv4')
        inst_id = instance_meta.get('instance-id')
        LOG_HISTORY.add_log("instance", inst_id)
        LOG_HISTORY.add_log("instance_ip", inst_ip)
        LOG_HISTORY.add_log("instance_id", RANDOM_HASH)
        # try:
        #     date = DATESTAMP.split("-")
        #     formatted_date = "{}/{}/{}/".format(date[2], date[1], date[0])
        #     instance_log_path = "http://sqs-tools.contentanalyticsinc.com/get-file/?file=" \
        #                         "{}{}____{}____remote_instance_starter2.log".format(
        #                         formatted_date, DATESTAMP, RANDOM_HASH)
        #     LOG_HISTORY.add_log("instance_log_path", instance_log_path)
        # except Exception as e:
        #     logger.info("Error formatting instance log path {}".format(e))
        logger.info("IMPORTANT: ip: %s, instance id: %s", inst_ip, inst_id)
    set_global_variables_from_data_file()
    redis_db = connect_to_redis_database(redis_host=REDIS_HOST,
                                         redis_port=REDIS_PORT)
    global MAX_SLOTS
    global MAX_TRIES_TO_GET_TASK
    tasks_taken = []
    # dict in format: {job_id:slots_num}
    current_tasks_running = {}
    options = {}
    if not daemon_is_restarted():
        # increment quantity of instances spinned up during the day.
        increment_metric_counter(INSTANCES_COUNTER_REDIS_KEY, redis_db)
        tries_left = MAX_TRIES_TO_GET_TASK
        branch = None
        task_data = None
        queue = None
        skip_first_getting_task = False
    else:
        options = load_options_after_restart()
        # try:
        #     max_tries = int(options.get('max_tries', MAX_TRIES_TO_GET_TASK))
        # except Exception as e:
        #     logger.warning('Error while load `max_tries` from old options. '
        #                    'ERROR: %s' % str(e))
        tries_left = MAX_TRIES_TO_GET_TASK
        branch = options.get('branch')
        task_data, queue = prepare_queue_after_restart(options)
        TASK_QUEUE_NAME = options.get('TASK_QUEUE_NAME')
        skip_first_getting_task = True
    try:
        listener = Listener(LISTENER_ADDRESS)
    except AuthenticationError:
        listener = None

    if not listener:
        logger.error('Socket auth failed!')
        raise Exception  # to catch exception and write end marker

    if not os.path.exists(os.path.expanduser(JOB_OUTPUT_PATH)):
        logger.debug("Create job output dir %s",
                     os.path.expanduser(JOB_OUTPUT_PATH))
        os.makedirs(os.path.expanduser(JOB_OUTPUT_PATH))

    def is_end_billing_instance_time():
        if not get_instance_billing_limit_time() or \
                        get_uptime() > get_instance_billing_limit_time():
            return False
        logger.info('Instance execution time limit.')
        return True

    def is_all_tasks_finished(tasks):
        return all([_.is_finished() for _ in tasks])

    def send_tasks_status(tasks):
        return [_.send_current_status_to_sqs()
                for _ in tasks if not _.is_finished()]

    def stop_not_finished_tasks(tasks):
        for _ in tasks:
            if not _.is_finished():
                _.stop()
        time.sleep(15)
        logger.info('Reporting stopped tasks')
        for _ in tasks:
            if not _.is_finished():
                try:
                    logger.info(_.process.stdout.read())
                    logger.info(_.process.stderr.read())
                except:
                    logger.warning('Unable to retrieve logs from task')

    def log_tasks_results(tasks):
        logger.info('#' * 10 + 'START TASKS REPORT' + '#' * 10)
        [logger.info(_.report()) for _ in tasks]
        logger.info('#' * 10 + 'FINISH TASKS REPORT' + '#' * 10)

    def get_slots_number(task_data):
        logger.info('Task {} branch is {}, assigning slots_number...'.format(
            task_data.get("task_id"), get_branch_for_task(task_data) or "sc_production"))

        selenium_list = ["checkout", "url2screenshot", "heb_", "csv_shelf"]
        try:
            site_name = task_data.get("site")
            task_quantity = task_data.get('cmd_args', {}).get('quantity', 20)
            parallel_screenshot = ScrapyTask(None, task_data, None).is_screenshot_job()
            with_best_seller_ranking = task_data.get('with_best_seller_ranking', None)
            if any([s for s in selenium_list if s in site_name]):
                slots_number = 15
                logger.info('Selenium task, slots_number set to {}'.format(slots_number))
            elif with_best_seller_ranking:
                slots_number = 10
                logger.info('Task with bestseller ranking, slots_number set to {}'.format(slots_number))
            elif parallel_screenshot:
                slots_number = 20
                logger.info('Parallel screenshot task, slots_number set to {}'.format(slots_number))
            elif "shelf_urls" in site_name:
                slots_number = 10
                logger.info('Shelf task, slots_number set to {}'.format(slots_number))
            elif "searchterms_str" in task_data:
                if task_quantity <= 100:
                    slots_number = 10
                elif 100 < task_quantity <= 300:
                    slots_number = 15
                elif 300 < task_quantity <= 600:
                    slots_number = 20
                elif 600 < task_quantity:
                    slots_number = 30
                else:
                    slots_number = 30
                logger.info('Search term task, quantity: {}, slots_number set to {}'.format(
                    task_quantity, slots_number))
            else:
                slots_number = 1
                logger.info('Single-url task, slots_number set to {}'.format(slots_number))
        except Exception as e:
            slots_number = 1
            logger.info('Exception {}, slots_number set to {}'.format(e, slots_number))
        return slots_number

    def get_instance_tag_value(tag_name):
        try:
            i_meta = get_instance_metadata()
            i_id = i_meta.get('instance-id')
            logger.info('Getting instance tag {} value for instance {}'.format(tag_name, i_id))
            ec2_conn = boto.connect_ec2()
            instances_list = ec2_conn.get_only_instances(instance_ids=[i_id])
            if instances_list:
                all_tags_dict = instances_list[0].tags
                tag_value = all_tags_dict.get(tag_name)
            else:
                tag_value = None
        except Exception as e:
            logger.info('Failed getting instance tag {} : {}'.format(tag_name, e))
            return
        else:
            return tag_value

    def get_actual_branch():
        git_command = "git symbolic-ref --short HEAD"
        output = Popen(git_command, shell=True, stdout=PIPE, close_fds=True)
        return str(output.communicate()[0])


    attributes = 'SentTimestamp'  # additional data to get with sqs messages
    add_timeout = 120  # add to visibility timeout
    # names of the queues in SQS, ordered by priority
    q_keys = ['urgent', 'production', 'test', 'dev']
    # Need this to not have a downtime if all instances will restart at same time
    MIN_UPTIME_REALTIME = random.randint(3000, 3300)
    MIN_UPTIME_PROD = random.randint(1020, 1500)
    # TODO make instance receive queue/queues and branch from instance tag
    # Implement separate cluster for realtime queue
    if TEST_MODE:
        LOG_HISTORY.add_log("queues", ["LOCAL_TEST_PLACEHOLDER_QUEUE"])
        MIN_UPTIME = MIN_UPTIME_REALTIME
    else:
        # Check if instance is in separate testing cluster
        instance_tag_value = get_instance_tag_value(tag_name="input_queue")
        LOG_HISTORY.add_log("instance_tag_{}".format("input_queue"), instance_tag_value)
        if instance_tag_value == "sqs_ranking_spiders_qa_test":
            logger.info('Instance is in testing cluster, will use sqs_ranking_spiders_qa_test queue')
            q_keys = ['qa_test']
            MIN_UPTIME = MIN_UPTIME_PROD
        elif instance_tag_value == "sqs_ranking_spiders_tasks_realtime":
            logger.info('Instance is in realtime cluster, will use only sqs_ranking_spiders_tasks_realtime queue')
            q_keys = ['realtime']
            MIN_UPTIME = MIN_UPTIME_REALTIME
        else:
            logger.info('Instance is IN PRODUCTION cluster, proceeding normally')
            MIN_UPTIME = MIN_UPTIME_REALTIME
        LOG_HISTORY.add_log("queues", q_keys)
        LOG_HISTORY.add_log("min_uptime", MIN_UPTIME)
    q_ind = 0  # index of current queue
    if daemon_is_restarted():
        LOG_HISTORY.add_log("is_restarted", True)
    else:
        LOG_HISTORY.add_log("is_restarted", False)
    # try to get tasks, until max number of tasks is reached or
    # max number of tries to get tasks is reached
    # making sure instance runs at least 50 minutes
    current_uptime = get_uptime()
    actual_branch = get_actual_branch()
    if daemon_is_restarted():
        logger.info('Actual branch from cmd after restart: {}'.format(actual_branch))
    else:
        logger.info('Actual branch from cmd: {}'.format(actual_branch))
    while (tries_left >= 0 or current_uptime <= MIN_UPTIME) and not is_end_billing_instance_time():
        current_uptime = get_uptime()
        logger.info('#'*10)
        current_uptime_formatted = time.strftime("%H:%M:%S", time.gmtime(current_uptime))
        logger.info('Instance uptime: {}'.format(current_uptime_formatted))
        if tries_left == 0 and current_uptime <= MIN_UPTIME:
            # instance is about to finish but run less than hour
            logger.info('Instance uptime is less than {} minutes - taking another task'.format(int(MIN_UPTIME/60)))
            tries_left += 1
            MAX_TRIES_TO_GET_TASK += 1

        logger.info('Total tasks taken since start: {}, tries left: {}'.format(len(tasks_taken), tries_left))

        # free slots for finished tasks
        all_finished_tasks_ids = [t.task_data.get("task_id") for t in tasks_taken if t.is_finished()]
        if all_finished_tasks_ids:
            finished_this_iter = [x for x in all_finished_tasks_ids if x in current_tasks_running]
            if finished_this_iter:
                logger.info("Tasks {} are finished, freeing slots".format(finished_this_iter))
            for task_to_del in finished_this_iter:
                del current_tasks_running[task_to_del]

        logger.info("Current running tasks (id and slots taken): {}".format(current_tasks_running))

        # check if enough slots available
        current_slots = sum(current_tasks_running.values())
        free_slots = MAX_SLOTS - current_slots
        logger.info("Slots used/Max slots: {}/{} Slots available: {}".format(current_slots, MAX_SLOTS, free_slots))
        logger.info('#'*10)

        # Skip if needed getting first task. After restarting task
        # in old options. For work scrapy daemon with a new source code
        # from new branch and with old task.
        if not skip_first_getting_task or not task_data:
            TASK_QUEUE_NAME = QUEUES_LIST[q_keys[q_ind]]
            logger.info('Trying to get task from {}, try #{}'.format(TASK_QUEUE_NAME, MAX_TRIES_TO_GET_TASK - tries_left))
            LOG_HISTORY.increase_counter_log("attempts", start_value=1)
            if TEST_MODE:
                msg = test_read_msg_from_fs(TASK_QUEUE_NAME)
            else:
                msg = read_msg_from_sqs(
                    TASK_QUEUE_NAME, add_timeout, attributes)
                    # TASK_QUEUE_NAME, tries_left + add_timeout, attributes) - test and uncomment?
            tries_left -= 1
            if msg is None:  # no task
                # if failed to get task from current queue,
                # then change it to the following value in a circle
                if q_ind < len(q_keys) - 1:
                    q_ind += 1
                else:
                    q_ind = 0
                time.sleep(3)
                continue
            task_data, queue = msg
        else:
            skip_first_getting_task = False

        if not task_data or not queue:
            continue
        if not tasks_taken and ENABLE_TO_RESTART_DAEMON:
            options['max_tries'] = tries_left
            options['TASK_QUEUE_NAME'] = TASK_QUEUE_NAME

        logger.info("Task message was successfully received.")

        # Add some data to command line for logging
        if "cmd_args" in task_data:
            task_data["cmd_args"]["sqs_input_queue"] = TASK_QUEUE_NAME
        else:
            task_data["cmd_args"] = {"sqs_input_queue": TASK_QUEUE_NAME}

        logger.info("Whole tasks msg: %s", str(task_data))
        # prepare to run task
        # check if task with such id is already taken,
        # to prevent running same task multiple times
        if is_task_taken(task_data, tasks_taken):
            logger.warning('Duplicate task %s, skipping.',
                           task_data.get('task_id'))
            continue

        if not tasks_taken:
            # get git branch from first task, all tasks should
            # be in the same branch
            if not daemon_is_restarted():
                branch = get_branch_for_task(task_data)
                switch_branch_if_required(task_data)
                options['branch'] = branch
                options['task_data'] = task_data
                options['queue'] = store_queue_for_restart(queue)
                if branch and get_actual_branch_from_cache() != branch and ENABLE_TO_RESTART_DAEMON:
                    logger.info('Daemon IS NOT restarted and WILL be restarted to {}'.format(branch))
                    save_options_for_restart(options)
                    listener.close()
                    restart_scrapy_daemon()
                else:
                    branch_name, build = get_and_save_branch_info("/tmp/branch_info.txt")
                    logger.info('Daemon IS NOT restarted and WONT be restarted: {} {}'.format(branch_name, build))
                    LOG_HISTORY.add_log("git_branch", branch_name)
                    LOG_HISTORY.add_log("build", build)
            else:
                branch_name, build = get_and_save_branch_info("/tmp/branch_info.txt")
                logger.info('Daemon IS restarted: {} {}'.format(branch_name, build))
                LOG_HISTORY.add_log("git_branch", branch_name)
                LOG_HISTORY.add_log("build", build)
        elif not is_same_branch(get_branch_for_task(task_data), branch):
            # make sure all tasks are in same branch
            logger.info("Task {} branch is {} - different than first task branch, skipped".format(
                task_data.get("task_id"), get_branch_for_task(task_data) or "sc_production"))
            queue.reset_message()
            continue
        elif is_same_branch(get_branch_for_task(task_data), branch):
            slots_num = get_slots_number(task_data)
            logger.info("Checking if enough slots available")
            logger.info("Task {} slots number {}".format(task_data.get("task_id"), slots_num))
            if free_slots < slots_num:
                logger.info("Not enough slots for the task, skipping")
                queue.reset_message()
                continue

        # Store jobs metrics
        store_tasks_metrics(task_data, redis_db)
        # start task
        # if started, remove from the queue and run
        task = ScrapyTask(queue, task_data, listener)
        task_id = (task.task_data.get("task_id"))
        LOG_HISTORY.add_list_log('tasks_taken_ids', str(task_id))
        #TODO rework this
        if not LOG_HISTORY.data.get("instance_log_path") or not LOG_HISTORY.data.get("instance_id"):
            save_path = task.get_output_path()
            LOG_HISTORY.add_log("instance_id", get_instance_id_from_path(save_path))
            LOG_HISTORY.add_log("instance_log_path", get_instance_log_path(save_path))
        if not task.is_valid():
            # remove task from queue, fields are invalid

            logger.warning('Removing task %s_%s from the queue because of invalid fields',
                           task_data.get('server_name'),
                           task_data.get('task_id'))
            task.queue.task_done()
            logger.error(task.report())

            del task
            continue
        # check for cached response
        if task.get_cached_result(TASK_QUEUE_NAME):
            LOG_HISTORY.increase_counter_log("cached_tasks_counter")
            # if found response in cache, upload data, delete task from sqs
            task.queue.task_done()
            notify_cache(task.task_data, is_from_cache=True)
            del task
            continue
        if task.start():
            current_tasks_running[task_data.get("task_id")] = get_slots_number(task_data)
            tasks_taken.append(task)
            task.run()
            logger.info(
                'Task %s started successfully, removing it from the queue',
                task.task_data.get('task_id'))
            LOG_HISTORY.increase_counter_log("tasks_started_counter")
            LOG_HISTORY.increase_counter_log("non_cached_tasks_counter")
            if task.is_screenshot_job():
                task.start_screenshot_job_if_needed()
            task.queue.task_done()
            notify_cache(task.task_data, is_from_cache=False)
        else:
            logger.error('Task #%s failed to start. Leaving it in the queue.',
                         task.task_data.get('task_id', 0))
            # remove task from queue, if it failed many times
            if log_failed_task(task.task_data):
                logger.warning('Removing task %s_%s from the queue due to too '
                               'many failed tries.',
                               task_data.get('server_name'),
                               task_data.get('task_id'))
                task.queue.task_done()
            logger.error(task.report())
    if not tasks_taken:
        logger.warning('No any task messages were found.')
        logger.info('Scrapy daemon finished.')
        return
    logger.info('Total tasks received: %s', len(tasks_taken))
    # wait until all tasks are finished or max wait time is reached
    # report each task progress after that and kill all tasks
    #  which are not finished in time
    # for _t in tasks_taken:
    #     logger.info('For task %s, max allowed running time is %ss', (
    #         _t.task_data.get('task_id'), _t.get_total_wait_time()))
    max_wait_time = max([t.get_total_wait_time() for t in tasks_taken]) or 160

    logger.info('Max allowed running time is %ss', max_wait_time)
    step_time = 30
    # loop where we wait for all the tasks to complete
    try:
        for i in xrange(0, max_wait_time, step_time):
            if is_all_tasks_finished(tasks_taken):
                logger.info('All tasks finished.')
                break
            send_tasks_status(tasks_taken)
            time.sleep(step_time)
            logger.info('Server statistics: ' + str(statistics.report_statistics()))
            shut_down_instance_if_swap_used()
        else:
            logger.error('Some of the tasks not finished in allowed time, '
                         'stopping them.')
            stop_not_finished_tasks(tasks_taken)
        time.sleep(20)
    except KeyboardInterrupt:
        stop_not_finished_tasks(tasks_taken)
        raise Exception
    listener.close()
    log_tasks_results(tasks_taken)
    # tasks_taken_ids = []
    # for t in tasks_taken:
    #     task_id = (t.task_data.get("task_id"))
    #     tasks_taken_ids.append(task_id)
    # LOG_HISTORY.add_log("tasks_taken_ids", tasks_taken_ids)
    # tasks_taken_stats = {}
    # #TODO add more useful stats here
    # for t in tasks_taken:
    #     task_id = (t.task_data.get("task_id"))
    #     tasks_taken_stats[task_id] = {"site": t.task_data.get("site"),
    #                                   "server_name": t.task_data.get("server_name"),
    #                                   "max_wait_time": t.get_total_wait_time()}
    # LOG_HISTORY.add_log("tasks_taken_stats", tasks_taken_stats)
    LOG_HISTORY.add_log("scrapy_daemon_version", "v3")
    # instance uptime in minutes
    current_uptime = get_uptime()
    LOG_HISTORY.add_log("instance_uptime", int(current_uptime/60))
    # calculate performance metrics
    try:
        instance_uptime_in_hours = round(current_uptime/60/60, 2)
        tasks_started_per_instance = LOG_HISTORY.data.get("tasks_started_counter")
        attempts = LOG_HISTORY.data.get("attempts")
        succesfull_attempts_rate = round(tasks_started_per_instance/attempts, 4)
        # adjustment needed because sometimes there is not enough tasks in queue
        # and this leads to a lot of failed attempts
        # and in other times, all attempts are
        tasks_started_per_hour = round(tasks_started_per_instance/instance_uptime_in_hours, 4)
    except Exception as e:
        logger.error('Error calculating performance metrics, {}'.format(traceback.format_exc()))
    else:
        LOG_HISTORY.add_log("succesfull_attempts_rate", succesfull_attempts_rate)
        LOG_HISTORY.add_log("tasks_started_per_hour", tasks_started_per_hour)
    #TODO maybe add separate metrics for selenium and non-selenium tasks?
    if not TEST_MODE:
        logger.debug('Sending logstash stats:')
        LOG_HISTORY.send_log()
    else:
        logger.debug('TEST_MODE is on, logstash stats:')
        logger.debug(pprint.pformat(LOG_HISTORY.data))

    # TODO: wait till all Selenium processes are finished? implement or not?
    # write finish marker
    # DO NOT CHANGE THIS STRING, USED ELSEWHERE
    logger.info('Scrapy daemon finished.')


def prepare_test_data():
    # only for local-filesystem tests!
    # prepare incoming tasks
    tasks = [
        dict(
            task_id=4443, site='walmart', branch_name='CON-30613-ConcurrencyRework', searchterms_str='iphone',
            server_name='test_server_name', with_best_seller_ranking=False,
            cmd_args={'quantity': 15}, attributes={'SentTimestamp': '1443426145373'}
        ),
        dict(
            task_id=4444, site='amazon', branch_name='CON-30613-ConcurrencyRework', searchterms_str='iphone',
            server_name='test_server_name', with_best_seller_ranking=False,
            cmd_args={'quantity': 25}, attributes={'SentTimestamp': '1443426145373'}
        ),
        dict(
            task_id=4445, branch_name='CON-30613-ConcurrencyRework', site='target', searchterms_str='iphone',
            server_name='test_server_name', with_best_seller_ranking=True,
            cmd_args={'quantity': 10}, attributes={'SentTimestamp': '1443426145373'}
        ),
        dict(
            task_id=4446, site='walmart', branch_name='CON-30613-ConcurrencyRework',
            url='https://www.walmart.com/ip/Peppa-Pig-Family-Figures-6-Pack/44012553',
            server_name='test_server_name', with_best_seller_ranking=False,
            cmd_args={'make_screenshot_for_url': True}, attributes={'SentTimestamp': '1443426145373'}
        ),
        dict(
            task_id=4447, branch_name='CON-30613-ConcurrencyRework', site='amazon',
            url='https://www.amazon.com/Anki-000-00048-Cozmo/dp/B01GA1298S/',
            server_name='test_server_name', with_best_seller_ranking=False,
            cmd_args={'make_screenshot_for_url': False}, attributes={'SentTimestamp': '1443426145373'}
        ),
        dict(
            task_id=4448, branch_name='CON-30613-ConcurrencyRework', site='url2screenshot',
            url='https://www.amazon.com/s/ref=lp_10445813011_ex_n_2?rh=n%3A7141123011%2Cn%3A10445813011%2Cn%3A7147440011&bbn=10445813011&ie=UTF8&qid=1454105549',
            server_name='test_server_name_url2screenshot_', with_best_seller_ranking=False,
            attributes={'SentTimestamp': '1443426145373'}
        ),
        dict(
            task_id=4449, branch_name='CON-30613-ConcurrencyRework', site='url2screenshot',
            url='https://jet.com/product/Tide-Simply-Clean-and-Fresh-Laundry-Detergent-Refreshing-Breeze-89-Loads/1e18dd7034ab4d67bdc0e5f363516f58',
            server_name='test_server_name_url2screenshot_', with_best_seller_ranking=False,
            attributes={'SentTimestamp': '1443426145373'}
        ),
    ]
    files = [open('/tmp/' + q, 'w') for q in QUEUES_LIST.itervalues()]
    for fh in files:
        for msg in tasks:
            fh.write(json.dumps(msg, default=json_serializer) + '\n')
        fh.close()


def log_free_disk_space():
    """mostly for debugging purposes, shows result of 'df -h' system command"""
    cmd = 'df -h'
    p = Popen(cmd, shell=True, stdout=PIPE, close_fds=True)
    res = p.communicate()
    if res[0]:
        res = res[0]
    else:
        res = res[1]
    logger.warning('Disk usage statisticks:')
    logger.warning(res)


if __name__ == '__main__':
    if daemon_is_restarted():
        logger.info('Scrapy daemon is restarted.')
    if 'test' in [a.lower().strip() for a in sys.argv]:
        TEST_MODE = True
        prepare_test_data()
        CACHE_HOST = 'http://127.0.0.1:5000/'
        try:
            # local mode
            from sqs_ranking_spiders.fake_sqs_queue_class import SQS_Queue
        except ImportError:
            from repo.fake_sqs_queue_class import SQS_Queue
        logger.debug('TEST MODE ON')
        logger.debug('Faking the SQS_Queue class')
    else:
        # TODO: move the whole code for downloading geckodriver to post_starter_root.py and rebuild the AMI image
        if not os.path.exists('/home/spiders/geckodriver'):
            install_geckodriver()

    try:
        # More file descriptors to prevent running out of resources
        resource.setrlimit(resource.RLIMIT_NOFILE, (4096, 4096))
        main()
        log_free_disk_space()
    except Exception as e:
        LOG_HISTORY = LogHistory("scrapy_daemon")
        LOG_HISTORY.start_log()
        LOG_HISTORY.add_log("severity", 'exception')
        LOG_HISTORY.add_log("error_message", str(e))
        LOG_HISTORY.add_log("stack_trace", traceback.format_exc())
        if not TEST_MODE:
            instance_meta = get_instance_metadata()
            inst_ip = instance_meta.get('public-ipv4')
            inst_id = instance_meta.get('instance-id')
            LOG_HISTORY.add_log("instance", inst_id)
            LOG_HISTORY.add_log("instance_ip", inst_ip)
            LOG_HISTORY.add_log("instance_id", RANDOM_HASH)
            branch_name, build = get_and_save_branch_info("/tmp/branch_info.txt")
            LOG_HISTORY.add_log("git_branch", branch_name)
            LOG_HISTORY.add_log("build", build)
            LOG_HISTORY.send_log()
        else:
            logger.debug('TEST_MODE is on, logstash stats:')
            logger.debug(pprint.pformat(LOG_HISTORY.data))
        log_free_disk_space()
        logger.exception(e)
        # DO NOT CHANGE THIS STRING, USED ELSEWHERE
        logger.error('Finished with error.')  # write fail finish marker
        try:
            os.killpg(os.getpgid(os.getpid()), 9)
        except:
            pass
