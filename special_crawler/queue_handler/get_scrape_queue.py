#!/usr/bin/env python
"""
Gist : Scrape Queue -> Scrape -> Process Queue

"""

import aerospike
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import traceback
import urlparse
from collections import defaultdict
from datetime import datetime

import boto
from boto.s3.key import Key

from sqs_connect import SQS_Queue

sys.path.insert(1, os.path.join(sys.path[0], '..'))

import crawler_service  # noqa: E402
from spiders_shared_code.cacheutils import aerospike as aerospike_cache

from spiders_shared_code.log_history import LogHistory  # noqa: 402
from spiders_shared_code import utils  # noqa: 402
try:
    from raven import Client
except ImportError:
    pass
#from spiders_shared_code.cacheutils import utils as aerospike_utils ?


logger = logging.getLogger('basic_logger')

queue_names = {
    "Development": "dev_scrape",
    "UnitTest": "unit_test_scrape",
    "IntegrationTest": "integration_test_scrape",
    "RegressionTest": "test_scrape",
    "Demo": "demo_scrape",
    "Production": "production_scrape",
    "Urgent": "production_scrape_urgent",
    "Walmartfullsite": "walmart-fullsite_scrape",
    "Walmartondemand": "walmart-ondemand_scrape",
    "WalmartMPHome": "walmart-mp_home_scrape",
    "WalmartScrapeTO": "walmart-mp_scrapeto",
    "Productioncustomer": "production_customer_scrape",
    "wm_production_scrape": "wm_production_scrape",
    "walmart-mp1_scrape": "walmart-mp1_scrape",
    "walmart-mp2_scrape": "walmart-mp2_scrape",
    "walmart-mp3_scrape": "walmart-mp3_scrape",
    "walmart-mp-sub_scrape": "walmart-mp-sub_scrape"
}

INDEX_ERROR = "IndexError : The queue was really out of items, but the count "\
    "was lagging so it tried to run again."

FETCH_FREQUENCY = 60

MAX_RESPONSE_SIZE = 256000
RESPONSE_BUCKET_NAME = 'ch-responses'


def get_cache_instance(settings, domain):
    cache_ = settings
    if not cache_:
        return

    if domain not in cache_.get("include", []):
        return

    max_age = int(cache_.get('max-age', 0))
    if not max_age:
        return

    if not all([x in cache_ for x in ('host', 'port', 'namespace', 'table')]):
        return

    host, port = cache_['host'], int(cache_['port'])
    try:
        client = aerospike.client({'hosts': [(host, port)]}).connect()
    except Exception:
        logger.error('Unknown error!', exc_info=True)
    else:
        namespace, table = str(cache_['namespace']), str(cache_['table'])
        cache = aerospike_cache.AerospikeTTLCache(
            client, namespace, table, ttl=max_age, maxsize=100
        )
        return cache

def connect_to_response_bucket():
    try:
        conn = boto.connect_s3(is_secure=False)
        bucket = conn.get_bucket(RESPONSE_BUCKET_NAME, validate=False)

        bucket_location = bucket.get_location()

        if bucket_location:
            conn = boto.s3.connect_to_region(bucket_location)
            bucket = conn.get_bucket(bucket_name)

        return bucket

    except Exception as e:
        logger.warn('Error connecting to response bucket: %s %s' %
                    (type(e), e), exc_info=True)

def main(environment, scrape_queue_name, thread_id):
    logger.info("Starting thread %d" % thread_id)

    cache_config_file = 'cache.json'

    logger.info('Using cache config file: %s' % cache_config_file)

    raw_settings = utils.get_raw_settings(key_name=cache_config_file)

    # establish the scrape queue
    sqs_scrape = SQS_Queue(scrape_queue_name)

    proxy_config = {}
    last_fetch = datetime.min

    response_bucket = connect_to_response_bucket()

    git_branch = None
    build = None

    try:
        status = subprocess.check_output(['git', '--git-dir=/home/ubuntu/tmtext/.git', '--work-tree=/home/ubuntu/tmtext', 'status'])
        git_branch = re.search('On branch (.+)', status).group(1)

        last_commit = subprocess.check_output(['git', '--git-dir=/home/ubuntu/tmtext/.git', '--work-tree=/home/ubuntu/tmtext', 'log', '-1'])
        build = re.search('Date:\s+(.+)', last_commit).group(1)
    except Exception as e:
        print traceback.format_exc(e)

    # Continually pull off the SQS Scrape Queue
    while True:
        go_to_sleep = False

        if sqs_scrape.count() == 0:
            go_to_sleep = True

        if not go_to_sleep:
            try:
                # Get message from SQS
                message = sqs_scrape.get()
            except IndexError as e:
                # This exception will most likely be triggered because i
                # you were grabbing off an empty queue
                go_to_sleep = True
            except Exception as e:
                # Catch all other exceptions to prevent the whole
                # thing from crashing
                # TODO : Consider testing that sqs_scrape is still
                # live, and restart it if need be
                go_to_sleep = True
                logger.warn(e)

        if not go_to_sleep:
            try:
                logger.info('Received: thread %d message %s' %
                            (thread_id, message))

                # De-serialize to a json object
                message_json = json.loads(message)

                # Vars from the json object
                url = message_json['url']
                site = message_json['site']
                site_id = message_json['site_id']
                server_name = message_json['server_name']
                product_id = message_json['product_id']
                event = message_json['event']
                pl_name = message_json.get('pl_name')

                additional_requests = message_json.get('additional_requests')
                get_image_dimensions = message_json.get('get_image_dimensions')
                zip_code = message_json.get('zip_code')
                crawl_date = message_json.get('crawl_date')

                netloc = urlparse.urlparse(url).netloc
                if environment == 'Development':
                    settings = raw_settings.get("dev")
                else:
                    settings = raw_settings.get("production")

                lh = LogHistory('CH')
                lh.start_log()

                lh.add_log('sqs_input_queue', scrape_queue_name)
                lh.add_log('sqs_output_queue', '%s_process' % server_name)

                lh.add_log('git_branch', git_branch)
                lh.add_log('build', build)

                lh.add_log('url', url)
                lh.add_log('server_hostname',
                           message_json.get('server_hostname').replace('-', '_'))
                lh.add_log('pl_name', pl_name)

                sentry_client = init_sentry_client(
                    lh,
                    branch=git_branch,
                    hostname=message_json.get('server_hostname').replace('-', '_')
                )

                if (datetime.now() - last_fetch).seconds > FETCH_FREQUENCY:
                    amazon_bucket_name = 'ch-settings'
                    key_file = 'proxy_settings_master.cfg'

                    try:
                        S3_CONN = boto.connect_s3(is_secure=False)
                        S3_BUCKET = S3_CONN.get_bucket(amazon_bucket_name,
                                                       validate=False)
                        k = Key(S3_BUCKET)
                        k.key = key_file
                        proxy_config = json.loads(k.get_contents_as_string())

                        logger.info('Fetched proxy config: thread %d' %
                                    thread_id)
                        last_fetch = datetime.now()

                    except Exception as e:
                        logger.warn('Failed to fetch proxy config: thread %d'
                                    'error %s' % (thread_id, e), exc_info=True)

                cache = None
                max_retries = 1

                i = 0
                while i < max_retries:
                    i += 1

                    get_start = time.time()

                    # good enough reason to do so too
                    if cache is None:
                        cache = get_cache_instance(settings, domain=netloc)
                        if cache is not None:
                            lh.data.setdefault('cache', defaultdict(int))

                    try:
                        site = crawler_service.extract_domain(url)
                        lh.add_log('scraper_type', site)
                        if sentry_client:
                            sentry_client.context.merge({'tags': {'scraper_name': site, 'url': url}})

                        # create scraper class for requested site
                        site_scraper = crawler_service.SUPPORTED_SITES[site](
                            url = url,
                            additional_requests = additional_requests,
                            get_image_dimensions = get_image_dimensions,
                            proxy_config = proxy_config.get(site) or proxy_config.get('default'),
                            lh = lh,
                            cache = cache,
                            zip_code=zip_code,
                            sentry_client=sentry_client,
                            crawl_date=crawl_date
                        )

                        is_valid_url = site_scraper.check_url_format()

                        if hasattr(site_scraper, "INVALID_URL_MESSAGE"):
                            crawler_service.check_input(
                                url,
                                is_valid_url,
                                site_scraper.INVALID_URL_MESSAGE
                            )
                        else:
                            crawler_service.check_input(url, is_valid_url)

                        output_json = site_scraper.product_info()
                        lh.add_log('site_version', output_json.get('site_version'))

                        failure_cause = output_json.get('failure_type')

                        if failure_cause:
                            failure_cause = re.sub('[^\w\d_]', '', str(failure_cause))
                            lh.add_log('failure_cause', failure_cause)

                        lh.add_log('temporary_unavailable',
                                   output_json.get('product_info', {})
                                   .get('temporary_unavailable'))

                    except crawler_service.InvalidUsage as e:
                        logger.warn('Error extracting output json: %s %s' %
                                    (type(e), e.to_dict()), exc_info=True)
                        output_json = e.to_dict()
                        lh.add_log('failure_type', 'invalid url')

                    except Exception as e:
                        logger.warn('Error extracting output json: %s %s' %
                                    (type(e), e), exc_info=True)

                        loaded_in_seconds = round(time.time() - get_start, 2)

                        output_json = {
                            "error": str(e),
                            "date": datetime.strftime(datetime.now(),
                                                      '%Y-%m-%d %H:%M:%S'),
                            "status": "failure",
                            "page_attributes": {
                                "loaded_in_seconds": loaded_in_seconds
                            }
                        }

                        lh.add_list_log('errors', 'Error extracting output json: {}'.format(e))

                    finally:
                        if cache is not None:
                            cache.close(flush=True)  # method is called once

                    output_json['attempt'] = i

                    # If scraper response was successful, we're done
                    if not output_json.get('status') == 'failure':
                        break

                    # If failure was due to proxies
                    if output_json.get('failure_type') in ['max_retries', 'proxy']:
                        logger.info('GOT FAILURE TYPE %s for %s - RETRY %d' %
                                    (output_json.get('failure_type'), url, i))
                        max_retries = 10
                        # back off incrementally
                        time.sleep(60 * i)
                    else:
                        max_retries = 1

                output_json['url'] = url
                output_json['site_id'] = site_id
                output_json['product_id'] = product_id
                output_json['event'] = event
                output_json['pl_name'] = pl_name
                output_json['scraper_type'] = site

                output_message = json.dumps(output_json)

                path = "/" + datetime.utcnow().strftime('%Y/%m/%d') + "/"

                filename = str(int(time.time() * 10**6)) + '.json'
                filepath = (path + filename)

                # create new, smaller output json to send back to SQS
                new_output_json = {}

                core_output_keys = ['date', 'url', 'site_id', 'product_id', 'event', 'pl_name', 'scraper_type']

                for key in core_output_keys:
                    new_output_json[key] = output_json.get(key)

                for t in range(2):
                    try:
                        if not response_bucket:
                            response_bucket = connect_to_response_bucket()

                        k = Key(response_bucket)
                        k.key = filepath
                        k.set_contents_from_string(output_message)

                        new_output_json['s3_filepath'] = filepath
                        lh.add_log('s3_filepath', filepath)

                        break

                    except Exception as e:
                        response_bucket = None

                        logger.warn('Error uploading response to S3: %s %s' %
                                    (type(e), e), exc_info=True)

                else:
                    new_output_json['status'] = 'failure'
                    new_output_json['failure_type'] = 'Response too large'

                if sys.getsizeof(output_message) > MAX_RESPONSE_SIZE:
                    output_json = new_output_json
                    output_message = json.dumps(output_json)

                lh.add_log('status', output_json.get('status'))

                logger.info('Sending: url %s message %s' %
                            (url, output_message))

                # Add the scraped page to the processing queue ...
                sqs_process = SQS_Queue('%s_process' % server_name)
                sqs_process.put(output_message)
                # ... and remove it from the scrape queue
                sqs_scrape.task_done()

                logger.info("Sent: thread %d server %s url %s" %
                            (thread_id, server_name, url))

                logger.info('Sending log history in thread %d with value %s' %
                            (thread_id, lh.get_log()))

                # Send Log History
                lh.send_log()

            except Exception as e:
                logger.warn('Error: %s %s' % (type(e), e), exc_info=True)
                sqs_scrape.reset_message()

        time.sleep(1)

def init_sentry_client(lh, branch='', hostname=None):
    try:
        dsn = 'https://4117b57591b2403b8bfb7e7088caede4:8607e42cfc3b4a6fbb057a702553f9c2@sentry.io/222572'
        client = Client(dsn, install_sys_hook=False)
        config = {
            'tags':
                {
                    'scraper': 'CH',
                    'server_hostname': hostname,
                    'branch': branch
                }
        }
        config['tags']['git_branch'] = branch
        client.context.merge(config)
        return client
    except:
        print traceback.format_exc()
        lh.add_list_log('errors', 'Can\'t init sentry client: {}'.format(traceback.format_exc()))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # e.g., UnitTest, see dictionary of queue names
        environment = sys.argv[1]
        queue_name = "no queue"

        for k in queue_names:
            if environment == k:
                queue_name = queue_names[k]

        if queue_name != "no queue":
            logger.info("environment: %s" % environment)
            logger.info("using scrape queue %s" % queue_name)
            if environment != "UnitTest":
                threads = []
                for i in range(5):
                    logger.info("Creating thread %d" % i)
                    t = threading.Thread(target=main,
                                         args=(environment, queue_name, i))
                    threads.append(t)
                    t.start()
            else:
                main(environment, queue_name, -1)
        else:
            print "Environment not recognized: %s" % environment
    else:
        print "##" * 50
        print "This script receives URLs via SQS "\
            "and sends back the scraper response."
        print "Please input correct argument for the environment.\n"\
            "for ex: python get_scrape_queue.py 'UnitTest' "
        print "##" * 50
