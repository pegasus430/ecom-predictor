from __future__ import division

import datetime
import os
import sys
from multiprocessing.connection import Client
from socket import error as socket_error
from logging import WARNING, ERROR

from .settings import SENTRY_DSN
from raven import Client as SentryClient
from twisted.python import log
from spiders_shared_code.log_history import LogHistory
from spiders_shared_code.cacheutils import aerospike as aerospike_cache
from spiders_shared_code.cacheutils import utils as aerospike_utils
import aerospike
from boto.utils import get_instance_metadata
from scrapy import signals
from scrapy.http import TextResponse
from scrapy.exceptions import NotConfigured
from scrapy.xlib.pydispatch import dispatcher
from scrapy.utils.misc import load_object
from boto.s3.connection import S3Connection
from s3peat import S3Bucket, sync_to_s3  # pip install s3peat
import cStringIO
import gzip
import time
import cache
import settings
from cache_models import create_db_cache_record


CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(CWD, '..', '..', 'deploy'))
# sys.path.append(os.path.join(CWD, '..', 'spiders_shared_code', 'cacheutils'))

try:
    from cache_layer.cache_service import SqsCache
except ImportError:
    print 'ERROR: CANNOT IMPORT SQSCACHE PACKAGE!'


bucket_name = 'spiders-cache'


def report_stats(signal_name):
    """
    Decorator, which sends signal to the connection
    with the signal_name as name parameter two times.
    One before method execution with status 'started'.
    Second after method execution with status 'closed'
    :param signal_name: name of the signal
    """
    def wrapper(func):

        def send_signal(name, status):
            data = dict(name=name, status=status)
            SignalsExtension.CONNECTION.send(data)

        def wrapped(*args, **kwargs):
            if not SignalsExtension.CONNECTION:
                return
            # 1) report signal start
            send_signal(signal_name, SignalsExtension.STATUS_STARTED)
            # 2) execute method
            res = func(*args, **kwargs)
            # 3) report signal finish
            send_signal(signal_name, SignalsExtension.STATUS_FINISHED)
            # 4) return result
            return res

        return wrapped

    return wrapper


def _ip_on_spider_open(spider):
    server_ip = getattr(spider, 'server_ip', None)
    if not server_ip:
        return
    ip_fname = '/tmp/_server_ip'
    if not os.path.exists(ip_fname):
        with open(ip_fname, 'w') as fh:
            fh.write(server_ip)
    print('Server IP: %s' % server_ip)
    if hasattr(spider, 'log'):
        spider.log('Server IP: %s' % server_ip)


class RequestsCounter(object):
    __sqs_cache = None

    def __init__(self, *args, **kwargs):
        dispatcher.connect(RequestsCounter.__handler, signals.spider_closed)

    @classmethod
    def get_sqs_cache(cls):
        if cls.__sqs_cache is None:
            cls.__sqs_cache = SqsCache()
        return cls.__sqs_cache

    @staticmethod
    def __handler(spider, reason):
        spider_stats = spider.crawler.stats.get_stats()
        try:
            request_count = int(spider_stats.get('downloader/request_count'))
        except (ValueError, TypeError):
            request_count = 0
        if request_count:
            try:
                RequestsCounter.get_sqs_cache().db.incr(
                    RequestsCounter.get_sqs_cache().REDIS_REQUEST_COUNTER,
                    request_count
                )
            except Exception as e:
                print 'ERROR WHILE STORE REQUEST METRICS. EXP: %s', e

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)


def _s3_cache_on_spider_close(spider, reason):
    utcnow = datetime.datetime.utcnow()
    # upload cache
    bucket = S3Bucket(bucket_name, public=False)
    folder_path = cache.get_partial_request_path(
        settings.HTTPCACHE_DIR, spider, utcnow)
    if not os.path.exists(folder_path):
        print('Path to upload does not exist:', folder_path)
        return
    print('Uploading cache to', folder_path)
    try:
        # Upload file to S3
        sync_to_s3(
            directory=folder_path,
            prefix=os.path.relpath(folder_path, settings.HTTPCACHE_DIR),
            bucket=bucket,
            concurrency=20
        )
        uploaded_to_s3 = True
    except Exception as e:
        print('ERROR UPLOADING TO S3', str(e))
        pass
        uploaded_to_s3 = False
        #logger.error("Failed to load log files to S3. "
        #             "Check file path and amazon keys/permissions.")
    # create DB record
    if uploaded_to_s3:
        create_db_cache_record(spider, utcnow)
    # remove local cache
    # DO NOT CLEAR LOCAL CACHE on file upload - otherwise you may delete cache of
    #  a spider working in parallel!


class S3CacheUploader(object):

    def __init__(self, crawler, *args, **kwargs):
        # check cache map - maybe such cache already exists?
        enable_cache_upload = True
        utcdate = cache.UTC_NOW if cache.UTC_NOW else datetime.datetime.utcnow()
        utcdate = utcdate.date()
        print('Checking if cache already exists')
        cache_map = cache.get_cache_map(
            spider=crawler._spider.name, date=utcdate)
        if crawler._spider.name in cache_map:
            if utcdate in cache_map[crawler._spider.name]:
                if cache._get_searchterms_str_or_product_url() \
                        in cache_map[crawler._spider.name][utcdate]:
                    print('Cache for this date, spider,'
                          ' and searchterm already exists!'
                          ' Cache will NOT be uploaded!')
                    enable_cache_upload = False
        if enable_cache_upload:
            dispatcher.connect(_s3_cache_on_spider_close, signals.spider_closed)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)


def _download_s3_file(key):
    _local_cache_file = os.path.join(settings.HTTPCACHE_DIR, key.key)
    _dir = os.path.dirname(_local_cache_file)
    if not os.path.exists(_dir):
        os.makedirs(_dir)
    print('Downloading cache file', _local_cache_file)
    try:
        res = key.get_contents_to_filename(_local_cache_file)
    except Exception as e:
        print(str(e))


class S3CacheDownloader(object):

    def __init__(self, crawler, *args, **kwargs):
        _load_from = cache._get_load_from_date()
        _blocker_fname = '/tmp/_cache_spider_blocker'
        os.system("echo '1' > %s" % _blocker_fname)
        # remove local cache
        cache.clear_local_cache(settings.HTTPCACHE_DIR, crawler._spider,
                                _load_from)
        # download s3 cache
        # TODO: speed up by using cache_map from DB!
        conn = S3Connection()
        bucket = conn.get_bucket(bucket_name)
        partial_path = cache.get_partial_request_path(
            settings.HTTPCACHE_DIR, crawler._spider, _load_from)
        _cache_found = False
        _keys2download = []
        for key in bucket.list():
            if key.key.startswith(os.path.relpath(
                    partial_path, settings.HTTPCACHE_DIR)):
                _cache_found = True
                _keys2download.append(key)
        if not _cache_found:
            print('Cache is not found! Check the date param!')
            sys.exit(1)
        # TODO: fix! (threaded downloading hangs up for unknown reasons)
        """
        # init pool
        pool = workerpool.WorkerPool(size=10)
        # The ``download`` method will be called with a line from the second
        # parameter for each job.
        pool.map(_download_s3_file, _keys2download)
        # Send shutdown jobs to all threads, and wait until all the jobs have been completed
        pool.shutdown()
        pool.wait()
        """
        for key2download in _keys2download:
            _download_s3_file(key2download)
        print('Cache downloaded; ready for re-parsing the data, remove'
              ' %s file when you are ready' % _blocker_fname)
        while os.path.exists(_blocker_fname):
            import time
            time.sleep(0.5)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)


class SignalsExtension(object):

    STATUS_STARTED = 'opened'
    STATUS_FINISHED = 'closed'
    CONNECTION = None

    def __init__(self, crawler):
        # self.send_finish_signal('script_opened')
        pass

    def item_scraped(self, item, spider):
        SignalsExtension.CONNECTION.send(dict(name='item_scraped'))

    def item_dropped(self, item, spider, exception):
        SignalsExtension.CONNECTION.send(dict(name='item_dropped'))

    def spider_error(self, failure, response, spider):
        SignalsExtension.CONNECTION.send(dict(name='spider_error'))

    def spider_opened(self, spider):
        self.send_finish_signal('spider_opened')

    def spider_closed(self, spider):
        self.send_finish_signal('spider_closed')
        SignalsExtension.CONNECTION.close()

    def send_finish_signal(self, name):
        if not SignalsExtension.CONNECTION:
            print 'Finish signal:', name
        else:
            SignalsExtension.CONNECTION.send(dict(
                name=name, status=SignalsExtension.STATUS_FINISHED)
            )

    @classmethod
    def from_crawler(cls, crawler):
        if not crawler.settings.getbool('WITH_SIGNALS'):
            print 'pass signals ext'
            raise NotConfigured
        SignalsExtension.create_connection(('localhost', 9070))
        ext = cls(crawler)
        crawler.signals.connect(ext.spider_opened, signals.spider_opened)
        crawler.signals.connect(ext.spider_closed, signals.spider_closed)
        crawler.signals.connect(ext.item_scraped, signals.item_scraped)
        crawler.signals.connect(ext.item_dropped, signals.item_dropped)
        crawler.signals.connect(ext.spider_error, signals.spider_error)
        return ext

    @staticmethod
    def create_connection(address):
        print 'create connection'
        try:
            # raises after 20 secs of waiting
            SignalsExtension.CONNECTION = Client(address)
            print 'connection set'
        except socket_error:
            print 'no connection'
            raise NotConfigured


class IPCollector(object):

    def __init__(self, crawler, *args, **kwargs):
        dispatcher.connect(_ip_on_spider_open, signals.spider_opened)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)


class AerospikeCache(object):
    def __init__(self, host, port, namespace, table, max_age):
        self.client = aerospike.client({'hosts': [(host, port)]}).connect()
        self.cache = aerospike_cache.AerospikeTTLCache(
            self.client, str(namespace), str(table), max_age, maxsize=100
        )

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        if not settings.getbool('AEROSPIKECACHE_ENABLED', False):
            raise NotConfigured
        host = settings.get('AEROSPIKECACHE_HOST')
        port = settings.getint('AEROSPIKECACHE_PORT')
        table = settings.get('AEROSPIKECACHE_TABLE')
        namespace = settings.get('AEROSPIKECACHE_NAMESPACE')
        max_age = settings.getint('AEROSPIKECACHE_MAXAGE')
        if not all([host, port, namespace, table, max_age]):
            raise NotConfigured
        obj = cls(host, port, namespace, table, max_age)
        obj.crawler = crawler
        obj.stats = crawler.stats
        crawler.signals.connect(
            obj.spider_closed, signal=signals.spider_closed
        )
        return obj

    def __decompress(self, text):
        if isinstance(text, unicode):
            raise ValueError('text can\'t be unicode.')

        compressed = cStringIO.StringIO(text)
        with gzip.GzipFile(fileobj=compressed, mode='r') as gzipf:
            decompressed = gzipf.read()
        return decompressed

    def process_request(self, request, spider):
        # We are supporting GET only
        if request.method != 'GET':
            return

        # Prevents redirect fingerprint to be recalculated
        if 'aerospikecache_fingerprint' in request.meta:
            return

        if not hasattr(spider, 'canonicalize_url'):
            return

        url = spider.canonicalize_url(request.url)
        key = aerospike_utils.hostname_local_fingerprint(url)
        start_time = time.time()
        try:
            row = self.cache[key]
        except KeyError:
            self.stats.inc_value('aerospikecache/miss/count')
            self.stats.inc_value('aerospikecache/miss/time',
                                 time.time() - start_time)
            request.meta['aerospikecache_fingerprint'] = key
        else:
            url = row['url']
            status = row.get('status', 200)
            body = self.__decompress(row['body'])
            response_class = load_object(
                row.get('response_class', 'scrapy.http.HtmlResponse')
            )
            self.stats.inc_value('aerospikecache/hit/count')
            for key, value in row.items():
                self.stats.inc_value('aerospikecache/hit/bytes', len(key))
                if isinstance(value, int):
                    value = str(value)
                self.stats.inc_value('aerospikecache/hit/bytes', len(value))
            self.stats.inc_value('aerospikecache/hit/time',
                                 time.time() - start_time)
            if issubclass(response_class, TextResponse):
                return response_class(
                    url, status=status, body=body,
                    request=request, encoding='utf8'
                )
            return response_class(
                url, status=status, body=body, request=request
            )

    def __compress(self, text):
        if not isinstance(text, unicode):
            raise ValueError('text must be unicode.')

        compressed = cStringIO.StringIO()
        with gzip.GzipFile(fileobj=compressed, mode='w') as gzipf:
            gzipf.write(text.encode('utf8'))
        return compressed.getvalue()

    def process_response(self, request, response, spider):
        key = request.meta.get('aerospikecache_fingerprint', False)
        if key and response.status < 300:
            start_time = time.time()
            response_class = '{}.{}'.format(
                response.__class__.__module__,
                response.__class__.__name__
            )
            if hasattr(response, 'body_as_unicode'):
                body_unicode = response.body_as_unicode()
            else:
                try:
                    body_unicode = response.body.decode('utf8')
                except UnicodeError:
                    body_unicode = response.body.decode('latin1')
            data = {
                'response_class': response_class,
                'url': response.url,
                'status': response.status,
                'body': bytearray(self.__compress(body_unicode))
            }
            self.cache[key] = data
            self.cache.flush()
            self.stats.inc_value('aerospikecache/update/count')
            for key, value in data.items():
                self.stats.inc_value('aerospikecache/update/bytes', len(key))
                if isinstance(value, int):
                    value = str(value)
                self.stats.inc_value('aerospikecache/update/bytes', len(value))
            self.stats.inc_value(
                'aerospikecache/update/time', time.time() - start_time
            )
            # Prevents overriding the key on the same spider instance
            request.meta.pop('aerospikecache_fingerprint')
        return response

    def spider_closed(self, spider):
        self.cache.close(flush=True)


class LogstashExtension(object):
    def __init__(self, stats, crawlera_flag, log_path, results_path, use_proxies):
        log.addObserver(self.scrapy_error_handler)
        self.client = SentryClient(SENTRY_DSN, install_sys_hook=False)
        self.stats = stats
        self.crawlera_flag = crawlera_flag
        self.use_proxies = use_proxies
        self.log_history = LogHistory("SC")
        self.log_path = log_path
        self.results_path = results_path
        self.errors = []
        self.crawled_urls = []
        self.response_codes = {}
        self.responses_times = []
        self.received_time = time.time()
        self.walmart_temp_inla_counter = 0

    def scrapy_error_handler(self, data):
        # from warning to critical level
        log_level = data.get('logLevel')
        if log_level >= WARNING:
            error_list = {
                'severity': 'critical' if log_level >= ERROR else 'exception',
                'stack_trace': data.get('log_text'),
                'message': str(data.get('message'))
            }
            self.log_history.add_list_log('error_list', error_list)
        if log_level > WARNING and data.get('isError'):
            failure = data.get('failure')
        
            try:
                failure.raiseException()
            except:
                self.client.captureException()

    @staticmethod
    def get_instance_id_from_path(path):
        try:
            instance_id = path.split("____")[1]
        except:
            return None
        else:
            return instance_id

    @staticmethod
    def get_job_id_from_path(path):
        try:
            job_id = path.split("____")[2].split("--")[-1].strip("-")
        except:
            return None
        else:
            return job_id

    @staticmethod
    def get_server_name_from_path(path):
        try:
            server_name = path.split("____")[2].split("--")[0]
        except:
            return None
        else:
            return server_name

    @staticmethod
    def get_instance_log_path(path):
        try:
            path = path.split("/")[-1]
            date_raw = path.split("____")[0]
            date = date_raw.split("-")
            formatted_date = "{}/{}/{}/{}".format(date[2], date[1], date[0], date_raw)
            instance_id = path.split("____")[1]
            instance_log = "http://sqs-tools.contentanalyticsinc.com/" \
                           "get-file/?file={}____{}____remote_instance_starter2.log".format(formatted_date, instance_id)
        except:
            return None
        else:
            return instance_log

    @staticmethod
    def transform_to_download_path(path):
        # /home/spiders/job_output/14-02-2017____aizitt5yee83d2d8re5ts13h7s49____test-server--175333____chairs____johnlewis.log
        # http://sqs-tools.contentanalyticsinc.com/get-file/?file=2017/02/14/14-02-2017____aizitt5yee83d2d8re5ts13h7s49____test-server--175333____chairs____johnlewis.log.zip
        base_path = "http://sqs-tools.contentanalyticsinc.com/get-file/?file="
        try:
            path = path.replace('.log', '.log.zip')
            path = path.replace('.jl', '.csv.zip')
            path = path.replace('_bs.log.zip', '.log.zip')
            path = path.replace('_bs.csv.zip', '.csv.zip')
            path = path.split("/")[-1]
            date = path.split("____")[0].split("-")
            formatted_date = "{}/{}/{}/".format(date[2], date[1], date[0])
            download_path = "{}{}{}".format(base_path, formatted_date, path)
        except Exception as e:
            # TODO add logging
            return None
        else:
            return download_path

    def item_scraped(self, item, spider):
        if item.get('temporary_unavailable'):
            self.walmart_temp_inla_counter += 1
        self.log_history.add_log('failure_type', item.get('failure_type'))

    def spider_opened(self, spider):
        self.log_history.start_log()
        # Get branch info
        try:
            with open("/tmp/branch_info.txt", "r") as gittempfile:
                all_lines = gittempfile.readlines()
            self.log_history.add_log('git_branch', all_lines[0])
            self.log_history.add_log('build', all_lines[-1])
        except Exception:
            # TODO Add logging to middlewares/extensions
            pass

        url = getattr(spider, 'product_url', None)
        self.log_history.add_log('url', url)

        search_term = getattr(spider, 'searchterms', None)
        self.log_history.add_log('search_term', search_term)

        self.log_history.add_log('log_path', self.transform_to_download_path(self.log_path))
        self.log_history.add_log('results_path', self.transform_to_download_path(self.results_path))
        self.log_history.add_log('scraper_type', spider.name)
        self.log_history.add_log('scraper_name', spider.name)
        self.log_history.add_log('scraper', 'SC')
        self.log_history.add_log('crawlera_enabled', self.crawlera_flag)
        instance_meta = get_instance_metadata()
        inst_ip = instance_meta.get('public-ipv4')
        self.log_history.add_log('instance_ip', inst_ip)
        inst_id = instance_meta.get('instance-id')
        self.log_history.add_log('instance', inst_id)
        self.log_history.add_log('instance_log_path', self.get_instance_log_path(self.log_path))
        self.log_history.add_log('instance_id', self.get_instance_id_from_path(self.log_path))

        job_id = self.get_job_id_from_path(self.log_path)
        self.log_history.add_log('job_id', job_id)

        server_hostname = self.get_server_name_from_path(self.log_path)
        if server_hostname:
            server_name_escaped = server_hostname.replace("-", "_")
            self.log_history.add_log('server_hostname', server_name_escaped)

        slack_username = getattr(spider, 'slack_username', None)
        if slack_username:
            self.log_history.add_log('slack_username', slack_username)

        sqs_input_queue = getattr(spider, 'sqs_input_queue', None)
        if sqs_input_queue:
            self.log_history.add_log('sqs_input_queue', sqs_input_queue)

        pl_name = getattr(spider, 'pl_name', None) or getattr(spider, 'product_list_name', None)
        if pl_name:
            self.log_history.add_log('pl_name', pl_name)

        if server_hostname:
            sqs_output_queue = '{}sqs_ranking_spiders_output'.format(server_hostname)
            self.log_history.add_log('sqs_output_queue', sqs_output_queue)

        self.client.context.merge(
            {
                'tags': {
                    'job_id': job_id,
                    'git_branch': self.log_history.data.get('git_branch', '').strip(),
                    'scraper': 'SC',
                    'scraper_name': spider.name,
                    'server_hostname': server_hostname,
                    'url': url,
                    'search_terms': search_term
                }
            }
        )

    def spider_closed(self, spider):
        proxy_service = getattr(spider, 'proxy_service', None)
        if proxy_service:
            self.log_history.add_log('proxy_service', proxy_service.replace(":", "_"))
            self.log_history.add_log('proxy_config_filename', getattr(spider, 'proxy_config_filename', ""))
        self.log_history.add_log('proxy_config', getattr(spider, 'proxy_config', ""))
        all_stats = self.stats.get_stats()
        response_codes_dict = {}
        good_responses_codes_counter = 0
        bad_response_codes_counter = 0
        for key, value in all_stats.items():
            if "downloader/response_status_count" in key:
                code = key.split("/")[-1]
                if code[0] == "4" or code[0] == "5":  # all 4xx and 5xx codes
                    if "walmart" in spider.name and code == "520":
                        pass
                    else:
                        bad_response_codes_counter += 1
                else:
                    good_responses_codes_counter += 1
                response_codes_dict[code] = value
                self.log_history.add_log("response_code_{}".format(code), value)
        self.log_history.add_log("response_codes", response_codes_dict)

        # Calculate bad response codes percentage
        total_responses_count = bad_response_codes_counter + good_responses_codes_counter
        requests_number = self.stats.get_value('downloader/request_count')

        if total_responses_count:
            bad_responses_percentage = int((bad_response_codes_counter/total_responses_count)*100)
            good_responses_percentage = 100 - bad_responses_percentage  # for consistency
        elif requests_number:
            bad_responses_percentage = 100
            good_responses_percentage = 0
        else:
            bad_responses_percentage = 0
            good_responses_percentage = 0

        self.log_history.add_log('percent_bad_status_code', bad_responses_percentage)
        self.log_history.add_log('percent_good_status_code', good_responses_percentage)

        self.log_history.add_log('requests_number', requests_number)
        err_num = self.stats.get_value("log_count/ERROR", default=0)
        self.log_history.add_log('errors_number', err_num)
        self.log_history.add_log('max_response_time', self.stats.get_value("max_response_time"))
        self.log_history.add_log('min_response_time', self.stats.get_value("min_response_time"))
        self.log_history.add_log('item_scraped_count', self.stats.get_value("item_scraped_count"))
        self.log_history.add_log('total_bytes', self.stats.get_value("downloader/request_bytes"))
        self.log_history.add_log('use_proxies', self.use_proxies)

        avg_response_time = None
        if self.responses_times:
            avg_response_time = round(sum(self.responses_times)/len(self.responses_times), 2)
        self.log_history.add_log('response_time', avg_response_time)
        self.log_history.add_log('walmart_technical_difficulty', self.walmart_temp_inla_counter)

        stats = self.stats.get_stats()
        stats = {key.replace('.', '_'): value for key, value in stats.items()}
        stats['start_time'] = stats['start_time'].isoformat()
        stats['finish_time'] = stats['finish_time'].isoformat()
        self.log_history.data['scrapy_stats'] = stats

        self.log_history.send_log()
        self.client.context.clear()

    def response_received(self, response, request, spider):
        # When it comes from cache download_latency wont exist
        latency = request.meta.get('download_latency', 0.0)
        self.responses_times.append(latency)
        self.stats.max_value('max_response_time', round(latency, 2))
        self.stats.min_value('min_response_time', round(latency, 2))
        self.crawled_urls.append(response.url)

    @classmethod
    def from_crawler(cls, crawler):
        if not crawler.settings.getbool('LOGSTASH_ENABLED'):
            raise NotConfigured
        crawlera_flag = crawler.settings.getbool('CRAWLERA_ENABLED')
        log_path = crawler.settings.get('LOG_FILE')
        results_path = crawler.settings.get('FEED_URI')
        # new proxies with config in bucket
        use_proxies = crawler.settings.getbool('USE_PROXIES')
        obj = cls(crawler.stats, crawlera_flag, log_path, results_path, use_proxies)
        crawler.signals.connect(obj.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(obj.spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(obj.item_scraped, signal=signals.item_scraped)
        crawler.signals.connect(obj.response_received, signal=signals.response_received)
        return obj


if __name__ == '__main__':
    conn = S3Connection()
    bucket = conn.get_bucket(bucket_name)
    if 'clear_bucket' in sys.argv:  # be careful!
        if raw_input('Delete all files? y/n: ').lower() == 'y':
            for f in bucket.list():
                print '    removing', f
                bucket.delete_key(f.key)
        else:
            print('You did not type "y" - exit...')
    elif 'cache_map' in sys.argv:  # lists available cache
        cache_map = cache.get_cache_map()
        for spider, dates in cache_map.items():
            print '\n\n'
            print spider
            for date, searchterms in dates.items():
                print ' '*4, date
                for searchterm in searchterms:
                    print ' '*8, searchterm
    else:
        # list all files in bucket, for convenience
        from sqs_ranking_spiders.list_all_files_in_s3_bucket import \
            list_files_in_bucket
        for f in (list_files_in_bucket(bucket_name)):
            print f.key
