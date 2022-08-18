import copy
import datetime
import inspect
import io
import json
import logging
import os
import shutil
import socket
import time
import traceback
import urllib
import urllib2
import uuid
import zipfile
from importlib import import_module
from pkgutil import iter_modules

from billiard import current_process
import boto
from boto.s3.key import Key
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities


def load_spiders(path):

    def walk_modules(path):
        mods = []
        mod = import_module(path)
        mods.append(mod)
        if hasattr(mod, '__path__'):
            for _, subpath, ispkg in iter_modules(mod.__path__):
                fullpath = path + '.' + subpath
                if ispkg:
                    mods += walk_modules(fullpath)
                else:
                    submod = import_module(fullpath)
                    mods.append(submod)
        return mods

    spiders = {}

    for module in walk_modules(path):
        for obj in vars(module).itervalues():
            if inspect.isclass(obj)\
                    and issubclass(obj, SubmissionSpider)\
                    and obj.__module__ == module.__name__\
                    and getattr(obj, 'retailer', None):
                spiders[obj.retailer] = obj

    return spiders


def build_query_params(item):

    def recursion(item, base=None):
        pairs = []

        if hasattr(item, 'values'):
            for key, value in item.iteritems():
                quoted_key = urllib.quote(unicode(key))

                if base:
                    new_base = '{}[{}]'.format(base, quoted_key)
                else:
                    new_base = quoted_key

                pairs.extend(recursion(value, new_base))
        elif isinstance(item, list):
            for index, value in enumerate(item):
                if base:
                    new_base = "{}[{}]".format(base, index)
                    pairs.extend(recursion(value, new_base))
                else:
                    pairs.extend(recursion(value))
        else:
            quoted_item = urllib.quote(unicode(item))

            if item is not None:
                if base:
                    pairs.append("{}={}".format(base, quoted_item))
                else:
                    pairs.append(quoted_item)
        return pairs

    return '&'.join(recursion(item))


class SubmissionSpiderError(Exception):
    pass


class SubmissionSpider(object):

    retailer = None  # retailer name, mandatory property

    domain = None  # retailer submissions domain if supports
    sandbox_address = None  # must contain sandbox IP:PORT if supports
    bucket_name = None  # S3 bucket for uploading screenshots if supports

    driver_engine = 'phantomjs'
    user_agent = "Mozilla/5.0 (Windows NT 6.1; WOW64) " \
                 "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.94 Safari/537.36"

    media_export_api = 'http://image-download-api.contentanalyticsinc.com'

    def __init__(self, feed_id, resources_dir, sandbox=False, logger=None):
        self.feed_id = feed_id
        self._screenshots = []
        self._results = []

        self.data = {}

        self.sandbox = sandbox
        self.async_check_required = False

        self._resources_dir = os.path.join(resources_dir, feed_id)
        if not os.path.exists(self._resources_dir):
            os.makedirs(self._resources_dir)

        self.logger = self._add_log_file(logger or logging.getLogger(__name__))

        self.driver = self._init_driver() if self.driver_engine else None
        self.options = self._load_options_from_config()

    def _add_log_file(self, logger):
        child_logger = logger.getChild(self.feed_id)

        log_path = os.path.join(self._resources_dir, 'submission.log')

        log_format = logging.Formatter('%(asctime)s %(levelname)s:{feed_id}:%(message)s'.format(feed_id=self.feed_id))
        log_format.datefmt = '%Y-%m-%d %H:%M:%S'

        log_file = logging.FileHandler(log_path)
        log_file.setFormatter(log_format)
        log_file.setLevel(logging.DEBUG)
        child_logger.addHandler(log_file)

        return child_logger

    def close_log_file(self):
        for handler in self.logger.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                handler.close()
                self.logger.removeHandler(handler)

    def _init_driver(self):
        if self.driver_engine == 'phantomjs':
            try:
                desired_capabilities = DesiredCapabilities.PHANTOMJS
                desired_capabilities['phantomjs.page.settings.resourceTimeout'] = 60000

                if self.user_agent:
                    desired_capabilities['phantomjs.page.settings.userAgent'] = self.user_agent

                driver = webdriver.PhantomJS(desired_capabilities=desired_capabilities,
                                             service_args=['--ssl-protocol=any'])

                driver.set_window_size(width=1024, height=900)

                return driver
            except:
                self.logger.error('Can not init web driver: {}'.format(traceback.format_exc()))
        else:
            self.logger.error('Not supporting web driver engine: {}'.format(self.driver_engine))

    def _destroy_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                self.logger.error('Can not stop web driver: {}'.format(traceback.format_exc()))

    def _check_sandbox_availability(self):
        if self.sandbox_address:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                ip, port = self.sandbox_address.split(':')
                res = sock.connect_ex((ip, int(port)))

                sock.close()

                return res == 0
            except:
                self.logger.error('Can not check sandbox availability: {}'.format(traceback.format_exc()))

        return False

    def _api_url_iterator(self, server, criteria):
        endpoint = server.get('endpoint') or '/api/products'
        apply_product_changes = server.get('apply_product_changes') or 1

        base_api_url = '{server}{endpoint}?product[apply_product_changes]={apply_product_changes}&api_key={api_key}&{params}'

        products = criteria.get('filter', {}).get('products')

        if products:
            products_request_limit = 1000

            for i in range(0, len(products), products_request_limit):
                sub_criteria = copy.deepcopy(criteria)
                sub_criteria['filter']['products'] = products[i:i + products_request_limit]

                yield base_api_url.format(
                    server=server['url'],
                    endpoint=endpoint,
                    apply_product_changes=apply_product_changes,
                    api_key=server['api_key'],
                    params=build_query_params(sub_criteria)
                )
        else:
            yield base_api_url.format(
                server=server['url'],
                endpoint=endpoint,
                apply_product_changes=apply_product_changes,
                api_key=server['api_key'],
                params=build_query_params(criteria)
            )

    def _load_products(self, server, criteria):
        products = []

        missing_fields = {'url', 'api_key'} - set(server.keys())
        if missing_fields:
            self.logger.error('Missing mandatory server fields: {}'.format(', '.join(missing_fields)))
        else:
            for url in self._api_url_iterator(server, criteria):
                try:
                    self.logger.debug('Loading products: {}'.format(url))
                    res = urllib2.urlopen(url)
                except:
                    self.logger.error('Can not load products from MC {}: {}'.format(url, traceback.format_exc()))
                else:
                    if res.getcode() != 200:
                        self.logger.error('Can not load products from MC {}: response code {}, content: {}'.format(
                            url, res.getcode(), res.read()))
                    else:
                        content = res.read()

                        try:
                            data = json.loads(content)

                            if data.get('status') == 'error':
                                self.logger.error('Can not load products from MC (error {}): {}'.format(
                                    data.get('code'), data.get('message')))
                            else:
                                products.extend(data.get('products', []))
                        except:
                            self.logger.error('Can not parse response from MC: {}'.format(content))

        return products

    def perform_task(self, task_type, options, server=None, criteria=None):
        task = getattr(self, 'task_{}'.format(task_type), None)

        if not callable(task):
            return {'message': 'Not supporting submission type: {}'.format(task_type)}

        if self.sandbox and self.sandbox_address:
            if self._check_sandbox_availability():
                self.domain = 'http://{}'.format(self.sandbox_address)
            else:
                return {'message': 'Sandbox is not available: {}'.format(self.sandbox_address)}

        products = None

        if server and criteria:
            products = self._load_products(server, criteria)

            if not products:
                return {'message': 'Products are not found'}

        message = None

        if not self.driver_engine or self.driver:
            try:
                self.logger.info("Performing task '{}' by worker {} (pid {})".format(
                    task_type, current_process().index, current_process().pid))
                task_options = self.options.copy()
                task_options.update(options)

                task(task_options, products=products, server=server, criteria=criteria)
            except SubmissionSpiderError as e:
                self.logger.error('Task {} error: {}'.format(task_type, traceback.format_exc()))
                message = e.message
            except:
                self.logger.error('Can not perform task ({}): {}'.format(task_type, traceback.format_exc()))
                message = 'Submission could not be processed'

            self._destroy_driver()
        else:
            message = 'Submission could not be processed'

        result = {
            'message': message,
            'screenshots': self._upload_screenshots(),
            'results': self._upload_results(),
            'data': self.data
        }

        self.logger.info('Task result: {}'.format(result))

        return result

    def _upload_content_to_s3(self, key, content):
        if self.bucket_name:
            try:
                s3_conn = boto.connect_s3()
                s3_bucket = s3_conn.get_bucket(self.bucket_name, validate=False)

                s3_key = Key(s3_bucket)
                s3_key.key = datetime.datetime.now().strftime('%Y/%m/%d/{}'.format(key))
                s3_key.set_metadata("Content-Type", 'application/octet-stream')
                s3_key.set_contents_from_string(content)

                url = s3_key.generate_url(expires_in=0, query_auth=False)
                return url.split('?')[0]
            except:
                self.logger.error('Could not upload content {} to S3: {}'.format(key, traceback.format_exc()))
        else:
            self.logger.info('Bucket property is empty. Skip uploading {} to S3'.format(key))

    def _upload_results(self):
        if self._results:
            buf = io.BytesIO()

            with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
                for result in self._results:
                    if os.path.exists(result):
                        zip_file.write(result, os.path.basename(result))
                    else:
                        self.logger.warn('Result file {} does not exist'.format(result))

            return self._upload_content_to_s3('{}_results.zip'.format(self.feed_id), buf.getvalue())

    def get_file_path_for_result(self, name=None, append=True):
        result_path = os.path.join(self._resources_dir, name)

        if append:
            self._results.append(result_path)

        return result_path

    def take_screenshot(self, description=''):
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d__%H_%M_%S_%f')
        screenshot_path = os.path.join(self._resources_dir, '{}.png'.format(timestamp))

        if self.driver.save_screenshot(screenshot_path):
            self.logger.info('Screenshot: {} ({})'.format(description, screenshot_path))
            self._screenshots.append(screenshot_path)
        else:
            self.logger.error('Could not save screenshot:  {} ({})'.format(description, screenshot_path))

    def _upload_screenshots(self):
        if self._screenshots:
            buf = io.BytesIO()

            with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
                for screenshot in self._screenshots:
                    if os.path.exists(screenshot):
                        zip_file.write(screenshot, os.path.basename(screenshot))
                    else:
                        self.logger.warn('Screenshot {} does not exist'.format(screenshot))

            return self._upload_content_to_s3('{}_screenshots.zip'.format(self.feed_id), buf.getvalue())

    def _load_options_from_config(self, path='config.json'):
        options = {}

        try:
            with open(path) as config_file:
                options = json.load(config_file).get(self.retailer, {})
        except:
            self.logger.error('Can not read config file {}: {}'.format(path, traceback.format_exc()))

        return options

    def _export_media(self, criteria, server, options={}, media_type='images'):
        self.logger.info('Sending {} export request'.format(media_type))

        submission_data = {
            'server': server,
            'submission': {
                'type': media_type,
                'retailer': self.retailer,
                'options': options
            },
            'criteria': criteria
        }

        feed_id = uuid.uuid4().get_hex()

        submission_request = urllib2.Request(
            '{}/submission'.format(self.media_export_api),
            data=json.dumps(submission_data),
            headers={
                'X-API-KEY': 'alo4yu8fj30ltb3r',
                'X-FEED-ID': feed_id,
                'Content-Type': 'application/json'
            })

        response = json.loads(urllib2.urlopen(submission_request).read())

        if response.get('status') == 'error':
            raise SubmissionSpiderError('{} export request failed: {}'.format(media_type.capitalize(),
                                                                              response.get('message')))

        check_request = urllib2.Request(
            '{}/submission/{}'.format(self.media_export_api, feed_id),
            headers={
                'X-API-KEY': 'alo4yu8fj30ltb3r',
            }
        )

        start_time = time.time()

        while time.time() - start_time < 24*60*60:
            self.logger.debug('Checking export status')

            response = json.loads(urllib2.urlopen(check_request).read())

            if response.get('status') == 'error':
                raise SubmissionSpiderError('{} export request failed: {}'.format(media_type.capitalize(),
                                                                                  response.get('message')))
            elif response.get('status') == 'ready':
                images_url = response.get('file')

                if not images_url:
                    raise SubmissionSpiderError('No {} for submission'.format(media_type))

                self.logger.info('Loading {}: {}'.format(media_type, images_url))
                stream = urllib2.urlopen(images_url)

                images = self.get_file_path_for_result('{}.zip'.format(media_type), append=False)

                with open(images, 'wb') as images_file:
                    shutil.copyfileobj(stream, images_file)

                return images
            else:
                self.logger.debug('Status: {}'.format(response.get('status')))
                time.sleep(60)
        else:
            raise SubmissionSpiderError('{} export request timeout'.format(media_type.capitalize()))
