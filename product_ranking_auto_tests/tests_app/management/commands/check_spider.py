
# This file takes the given spider and performs its check.
# If no spidername given, it'll check a random spider
#

#assert False, 'read todo!'
# TODO:
# 1) alerts (special page + emails?)
# 2) better admin (list_fields, filters, status colors, all that stuff)
# 3) cron jobs file
# 4) removing old test runs and their files!
# 5) overall reports - just a page with list of spiders with status 'ok' and 'not ok'
#       (basically, testers will need to review the whole spider)
# 6) redirect page to go to #5 - like /spider-checks/costco_products/

import sys
import os
import re
import shutil
import time
import subprocess
import shlex
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from django.core.mail import send_mail
from django.core.urlresolvers import reverse_lazy

CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(1, os.path.join(CWD, '..', '..', '..'))

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from settings import (SPIDER_ROOT, MEDIA_ROOT, HOST_NAME)
from tests_app.models import (Spider, TestRun, FailedRequest, Alert,
                              ThresholdSettings)


ENABLE_CACHE = False


def run(command, shell=None):
    """ Runs the given command and returns its output """
    out_stream = subprocess.PIPE
    err_stream = subprocess.PIPE

    if shell is not None:
        p = subprocess.Popen(command, shell=True, stdout=out_stream,
                             stderr=err_stream, executable=shell)
    else:
        p = subprocess.Popen(command, shell=True, stdout=out_stream,
                             stderr=err_stream)
    (stdout, stderr) = p.communicate()

    return stdout, stderr


def spider_is_running(name, search_term=None):
    """ Checks if the given spider with name `name` is running.
        Optional arg `search_term` will narrow filtering,
        assuming we want to check that the spider with specified
        `name` AND `search_term` is running
    """
    if isinstance(name, unicode):
        name = name.encode('utf8')
    if search_term is None:
        all_processes = run('ps aux | grep scrapy')
    else:
        all_processes = run('ps aux | grep scrapy | grep "%s"' % search_term)
    all_processes = ''.join(all_processes)
    for proc_line in all_processes.split('\n'):
        if ' '+name in proc_line:
            if ' crawl ' in proc_line:
                return True


def get_spider_to_check(spider_to_get=None):
    """ Select random spider """
    if spider_to_get:
        # spider name arg given - select it
        spiders = Spider.objects.filter(active=True, name=spider_to_get.strip())
        if not spiders:
            print 'Spider %s not found in the DB' % spider_to_get
            sys.exit()
        spider = spiders[0]
    else:
        spiders = Spider.objects.filter(active=True).order_by('?')
        for spider in spiders:
            if spider_is_running(spider.name):
                continue
    # check one more time (there is a chance the test run
    # was stopped while switching between the requests)
    time.sleep(3)
    if not spider_is_running(spider.name):
        time.sleep(3)
        if not spider_is_running(spider.name):
            return spider


def list_spiders():
    """ Returns all the spider names and filenames
    :return:
    """
    spiders_dir = os.path.join(SPIDER_ROOT, 'product_ranking', 'spiders')
    for fname in os.listdir(spiders_dir):
        _full_fname = os.path.join(spiders_dir, fname)
        if not os.path.isfile(_full_fname):
            continue
        with open(_full_fname, 'r') as fh:
            spider_content = fh.read()
        spider_content = spider_content.replace(' ', '').replace('"', "'")
        spider_name = re.search("name=\'([\w_]+_products)\'", spider_content)
        if spider_name:
            yield fname, spider_name.group(1)


def get_scrapy_spider_and_settings(spider):
    """ Returns the Scrapy spider class and the validator class
        for the given Django spider """
    # import the spider module
    module_name = None
    _sn = spider.name if not isinstance(spider, (str, unicode)) else spider
    for fname, spider_name in list_spiders():
        if spider_name == _sn:
            module_name = fname.replace('.py', '')
    if module_name is None:
        return
    sys.path.append(os.path.join(SPIDER_ROOT))
    sys.path.append(os.path.join(SPIDER_ROOT, 'product_ranking'))
    sys.path.append(os.path.join(SPIDER_ROOT, 'product_ranking', 'spiders'))
    module = __import__(module_name)
    # get validator settings class and the spider class itself
    validator = None
    scrapy_spider = None
    for obj in dir(module):
        if type(getattr(module, obj, '')) == type:
            if hasattr(getattr(module, obj), 'test_requests'):
                validator = getattr(module, obj)
            elif hasattr(getattr(module, obj), 'test_urls'):
                validator = getattr(module, obj)
            elif (hasattr(getattr(module, obj), 'name')
                    and hasattr(getattr(module, obj), 'start_urls')):
                if not 'Base' in str(getattr(module, obj)):
                    if '.ProductsSpider' not in str(getattr(module, obj)):
                        scrapy_spider = getattr(module, obj)
    return scrapy_spider, validator


def create_failed_request(test_run, scrapy_spider, request, log_fname,
                          error, html_error=None):
    """ Just a convenient wrapper to avoid 'repeating myself' """
    today = timezone.now().strftime('%d_%m_%Y')
    output_dir = os.path.join(MEDIA_ROOT, 'output', test_run.spider.name)
    if not os.path.exists(os.path.join(output_dir, today)):
        os.makedirs(os.path.join(output_dir, today))
    fs_request = slugify(request)  # filesystem-friendly chars only
    output_file = os.path.join(output_dir, today,
                               str(test_run.pk)+'__'+fs_request+'.jl')
    log_file_db = os.path.join(output_dir, today,
                               str(test_run.pk)+'__'+fs_request+'.txt')
    if os.path.exists(scrapy_spider._validation_filename()):
        shutil.copy(scrapy_spider._validation_filename(), output_file)
    shutil.move(log_fname, log_file_db)
    fr = FailedRequest.objects.create(
        test_run=test_run, request=request,
        error=error, error_html=html_error if html_error else "",
        result_file=os.path.relpath(output_file, MEDIA_ROOT),
        log_file=os.path.relpath(log_file_db, MEDIA_ROOT)
    )
    return fr


def is_test_run_passed(test_run):
    """ Check if the test run has been passed
        (by percentage of allowed failed requests)
    """
    percent_of_failed_requests = test_run.spider\
        .get_percent_of_failed_requests()
    num_failed = test_run.num_of_failed_requests
    num_ok = test_run.num_of_successful_requests
    percent_failed = float(num_failed) / float(num_failed+num_ok) * 100
    return percent_failed < percent_of_failed_requests


def create_alert_if_needed(test_run_or_spider, wait_time='12hrs'):
    """ Create a DB alert if the threshold passed """
    if isinstance(test_run_or_spider, TestRun):
        spider = test_run_or_spider.spider
    else:
        spider = test_run_or_spider
    if not spider.is_error():
        return  # everything is okay?
    test_run = spider.get_last_failed_test_run()
    if test_run.test_run_alerts.count():
        return  # the alert has already been sent

    # do not create new alerts for this spider too often, lets not be annoying
    if not 'hrs' in wait_time:
        print 'invalid wait time'
        wait_time = 24
    wait_time = int(wait_time.replace('hrs', ''))
    wait_time = wait_time * 60 * 60  # convert to seconds
    _last_alert = test_run.get_last_alert()
    if _last_alert:
        if (_last_alert.when_created
                < timezone.now() + datetime.timedelta(seconds=wait_time)):
            return
    Alert.objects.create(test_run=test_run)


def check_spider(spider):
    test_run = TestRun.objects.create(status='running', spider=spider)
    scrapy_spider, spider_settings = get_scrapy_spider_and_settings(spider)

    test_requests = spider_settings.test_requests
    test_run_searchterm = _check_spider_searchterms(spider, scrapy_spider, test_requests, test_run)
    searchterm_passed = is_test_run_passed(test_run_searchterm)

    test_urls = getattr(spider_settings, 'test_urls', None)

    if test_urls:
        test_run_url = _check_spider_urls(spider, scrapy_spider, test_urls, test_run)
        url_passed = is_test_run_passed(test_run_url)
    else:
        url_passed = True

    if searchterm_passed and url_passed:
        test_run.status = 'passed'
        print ' '*3, 'test run PASSED'
    else:
        test_run.status = 'failed'
        print ' '*3, 'test run FAILED'
        create_alert_if_needed(test_run_searchterm)

    test_run.when_finished = timezone.now()
    test_run.save()


def _check_spider_searchterms(spider, scrapy_spider, test_requests, test_run):
    """ Running spider on searchterms """
    scrapy_spider = scrapy_spider()  # instantiate class to use its methods

    for req, req_range in test_requests.items():
        _log_fname = run_spider(
            spider=spider,
            mode='searchterm',
            arg=req,
            time_marker=timezone.now())
        errors = scrapy_spider.errors()
        html_errors = scrapy_spider.errors_html()
        output_data = scrapy_spider._validation_data()
        if errors:
            test_run.num_of_failed_requests += 1
            create_failed_request(test_run, scrapy_spider, req, _log_fname,
                                  errors, html_errors)
            print ' '*7, 'request failed:', req
        elif (isinstance(req_range, int)
                and len(output_data) != 0):
            test_run.num_of_failed_requests += 1
            create_failed_request(
                test_run, scrapy_spider, req, _log_fname,
                'must have empty output', '<p>must have empty output</p>')
            print ' '*7, 'request failed:', req
        elif (isinstance(req_range, (list, tuple))
                and not (req_range[0] < len(output_data) < req_range[1])):
            test_run.num_of_failed_requests += 1
            _msg = 'must have output in range %s but got %i results' % (
                        req_range, len(output_data))
            create_failed_request(
                test_run, scrapy_spider, req, _log_fname, _msg,
                '<p>' + _msg + '</p>')
            print ' '*7, 'request failed:', req
        else:
            test_run.num_of_successful_requests += 1
            print ' '*7, 'request passed:', req

        # remove the log file if it still exists (it happens if the request
        # did not fail but completed successfully, and the log file was not
        #  moved
        if os.path.exists(_log_fname):
            os.remove(_log_fname)

    return test_run


def _check_spider_urls(spider, scrapy_spider, test_urls, test_run):
    """ Running spider on searchterms """
    scrapy_spider = scrapy_spider(product_url=True)  # instantiate class to use its methods

    for url in test_urls:
        _log_fname = run_spider(
            spider=spider,
            mode='url',
            arg=url,
            time_marker=timezone.now())
        errors = scrapy_spider.errors()
        html_errors = scrapy_spider.errors_html()
        if errors:
            test_run.num_of_failed_requests += 1
            create_failed_request(test_run, scrapy_spider, url, _log_fname,
                                  errors, html_errors)
            print ' '*7, 'url failed:', url
        else:
            test_run.num_of_successful_requests += 1
            print ' '*7, 'url passed:', url

        # remove the log file if it still exists (it happens if the request
        # did not fail but completed successfully, and the log file was not
        # moved
        if os.path.exists(_log_fname):
            os.remove(_log_fname)

    return test_run


def wait_until_spider_finishes(spider):
    if spider_is_running(spider.name):
        time.sleep(1)


def run_spider(spider, mode, arg, time_marker):
    """ Executes spider
    :param spider: DB spider instance
    :param mode: mode of spider: url(product_url) or searchterm(searchterms_str)
    :param arg: value of searchterm or url
    :param time_marker: datetime
    :return: str, path to the temporary file
    """
    global ENABLE_CACHE
    old_cwd = os.getcwd()
    os.chdir(os.path.join(SPIDER_ROOT))
    # add `-a quantity=10 -a enable_cache=1` below for easider debugging
    scrapy_path = '/home/web_runner/virtual-environments/web-runner/bin/scrapy'
    if not os.path.exists(scrapy_path):
        scrapy_path = 'scrapy'

    if mode == 'searchterm':
        cmd, _log_filename = _run_spider_searchterm(scrapy_path, spider, arg, time_marker)
    elif mode == 'url':
        cmd, _log_filename = _run_spider_url(scrapy_path, spider, arg, time_marker)

    cmd += ' -s LOG_FILE=%s' % _log_filename
    cmd = str(cmd)  # avoid TypeError: must be encoded string without NULL ...
    subprocess.Popen(shlex.split(cmd), stdout=open(os.devnull, 'w')).wait()
    os.chdir(old_cwd)
    return _log_filename


def _run_spider_searchterm(scrapy_path, spider, search_term, time_marker):
    """ Executes spider
    :param spider: DB spider instance
    :param search_term: str, request to search
    :param time_marker: datetime
    :return: str, path to the temporary file
    """
    cmd = '{path} crawl {spider} -a searchterms_str="{searchterm}" -a validate=1'.format(
        path=scrapy_path,
        spider=spider.name,
        searchterm=search_term
    )
    if ENABLE_CACHE:
        cmd += ' -a enable_cache=1'
    if isinstance(time_marker, (datetime.date, datetime.datetime)):
        time_marker = slugify(str(time_marker))
    _log_filename = '/tmp/%s__%s__%s.log' % (
        spider.name, slugify(search_term), time_marker)
    return cmd, _log_filename


def _run_spider_url(scrapy_path, spider, url, time_marker):
    """ Executes spider
    :param spider: DB spider instance
    :param url: str, url to search
    :param time_marker: datetime
    :return: str, path to the temporary file
    """
    cmd = '{path} crawl {spider} -a product_url="{url}" -a validate=1'.format(
        path=scrapy_path,
        spider=spider.name,
        url=url
    )

    if ENABLE_CACHE:
        cmd += ' -a enable_cache=1'
    if isinstance(time_marker, (datetime.date, datetime.datetime)):
        time_marker = slugify(str(time_marker))
    _log_filename = '/tmp/%s__%s__%s.log' % (
        spider.name, slugify(url), time_marker)
    return cmd, _log_filename


class Command(BaseCommand):
    can_import_settings = True

    def add_arguments(self, parser):
        parser.add_argument('spider_name', nargs='?', type=str)
        parser.add_argument('enable_cache', nargs='?', type=str)

    def handle(self, *args, **options):
        global ENABLE_CACHE
        # check ThresholdSettings
        if not ThresholdSettings.objects.count():
            print 'Create at least one ThresholdSettings!'
            sys.exit()
        # get a spider to check
        spider = get_spider_to_check(options.get('spider_name', None))
        if options.get('enable_cache', None):
            ENABLE_CACHE = True
        if spider is None:
            print 'No active spiders in the DB, or all of them are running'
            sys.exit()
        print ' '*3, 'going to check spider %s:' % spider.name
        check_spider(spider)