import csv
import inspect
import logging
import os
import re
import time
import traceback
import uuid
import zipfile
import multiprocessing as mp
from threading import Thread
from importlib import import_module
from pkgutil import iter_modules

import lxml.etree
import requests


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
                    and issubclass(obj, SitemapSpider)\
                    and obj.__module__ == module.__name__\
                    and getattr(obj, 'retailer', None):
                spiders[obj.retailer] = obj

    return spiders


class SitemapSpiderError(Exception):
    pass


class SitemapSpider(object):

    retailer = None  # retailer name, mandatory property

    max_retries = 5

    def __init__(self, request_id, resources_dir, logger=None):
        self.request_id = str(request_id)
        self._mc_api_keys = {}
        self._results = []

        self._resources_dir = os.path.join(resources_dir,  self.request_id)
        if not os.path.exists(self._resources_dir):
            os.makedirs(self._resources_dir)

        self.logger = self._add_log_file(logger or logging.getLogger(__name__))

    def _add_log_file(self, logger):
        child_logger = logger.getChild(self.request_id)

        log_path = os.path.join(self._resources_dir, 'request.log')

        log_format = logging.Formatter('%(asctime)s %(levelname)s:{request_id}:%(message)s'.format(
            request_id=self.request_id))
        log_format.datefmt = '%Y-%m-%d %H:%M:%S'

        log_file = logging.FileHandler(log_path)
        log_file.setFormatter(log_format)
        log_file.setLevel(logging.DEBUG)
        child_logger.addHandler(log_file)

        return child_logger

    def perform_task(self, task_type, options):
        task = getattr(self, 'task_{}'.format(task_type), None)

        if not callable(task):
            return {'message': 'Not supporting request type: {}'.format(task_type)}

        message = None

        try:
            self.logger.info("Performing task '{}'".format(task_type))
            task(options)
        except SitemapSpiderError as e:
            self.logger.error('Task {} error: {}'.format(task_type, traceback.format_exc()))
            message = e.message
        except:
            self.logger.error('Can not perform task ({}): {}'.format(task_type, traceback.format_exc()))
            message = 'Request could not be processed'

        result = {
            'message': message,
            'results': self._save_results()
        }

        self.logger.info('Task result: {}'.format(result))

        return result

    def get_file_path_for_result(self, name=None, append=True):
        result_path = os.path.join(self._resources_dir, name)

        if append and result_path not in self._results:
            self._results.append(result_path)

        return result_path

    def _get_mc_api_key(self, server):
        if server not in self._mc_api_keys:
            self.logger.debug('Requesting API key for server {}'.format(server))
            api_url = 'https://{server}.contentanalyticsinc.com/api/token?' \
                      'username=api@cai-api.com&password=jEua6jLQFRjq8Eja'.format(server=server)
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            self._mc_api_keys[server] = data['api_key']
        return self._mc_api_keys[server]

    def save_failed_urls(self, failed_urls, name='failures.csv'):
        failed_urls_filename = self.get_file_path_for_result(name, append=False)
        with open(failed_urls_filename, 'w') as failed_urls_file:
            failed_urls_csv = csv.writer(failed_urls_file)
            for failed_url in failed_urls:
                if isinstance(failed_url, unicode):
                    failed_url = failed_url.encode('utf-8', errors='replace')
                failed_urls_csv.writerow([failed_url])

    def _save_results(self, name='results.zip'):
        if self._results:
            results_filename = self.get_file_path_for_result(name, append=False)

            with zipfile.ZipFile(results_filename, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zip_file:
                for result in self._results:
                    if os.path.exists(result):
                        zip_file.write(result, os.path.basename(result))
                        os.remove(result)
                    else:
                        self.logger.warn('Result file {} does not exist'.format(result))

            return name
        else:
            self.logger.info('Result is empty')

    def _parse_sitemap(self, url, raise_error=True, follow=True, **kwargs):
        urls = [url]

        if not kwargs.get('headers'):
            kwargs['headers'] = {'User-Agent': ''}

        while urls:
            next_url = urls.pop(0)

            self.logger.info('Loading sitemap: {}'.format(next_url))

            for _ in range(3):
                try:
                    response = requests.get(next_url, **kwargs)

                    if response.status_code != requests.codes.ok:
                        self.logger.error('Could not load sitemap: {}, code: {}'.format(next_url, response.status_code))
                    else:
                        break
                except:
                    self.logger.error('Could not load sitemap: {}'.format(traceback.format_exc()))
            else:
                if raise_error:
                    raise SitemapSpiderError('Could not load sitemap after retries')
                else:
                    self.logger.error('Could not load sitemap after retries')
                    continue

            xmlp = lxml.etree.XMLParser(recover=True, remove_comments=True, resolve_entities=False)
            root = lxml.etree.fromstring(response.content, parser=xmlp)
            type = self._clear_tag_name(root.tag)

            for elem in root.getchildren():
                for el in elem.getchildren():
                    name = self._clear_tag_name(el.tag)

                    if name == 'loc':
                        new_url = el.text.strip() if el.text else ''

                        if type == 'sitemapindex':
                            if follow:
                                urls.append(new_url)
                            else:
                                yield new_url
                        elif type == 'urlset':
                            yield new_url.encode('utf-8')

    def _clear_tag_name(self, name):
        return name.split('}', 1)[1] if '}' in name else name

    def _url_to_filename(self, url):
        return re.sub(r'\W', '_', url)[:150]

    def _save_response_dump(self, response, filename=None):
        if filename:
            if not filename.endswith('.html'):
                filename = '{}.html'.format(filename)
        else:
            filename = 'dump.html'

        with open(self.get_file_path_for_result(filename, append=False),
                  'w') as response_dump_file:
            response_dump_file.write(response.content)

    def _check_response(self, _response, raise_error=False, proxies=None, session=None):
        response = _response

        if response.status_code == requests.codes.ok:
            return True
        for i in range(self.max_retries):
            try:
                self.logger.warn('Response error {}, retry request: {}'.format(response.status_code, i + 1))

                time.sleep(i + 1)

                if session is None:
                    session = requests.session()

                    if proxies:
                        session.proxies = proxies

                response = session.send(response.request, timeout=(2, 60))

                if response.status_code == requests.codes.ok:
                    _response._content = response.content
                    return True
            except:
                self.logger.warn('Request error: {}'.format(traceback.format_exc()))
        else:
            dump_filename = uuid.uuid4().get_hex()

            self.logger.error('Response error {}, check dump: {}'.format(response.status_code, dump_filename))
            self._save_response_dump(response, dump_filename)

            if raise_error:
                raise SitemapSpiderError('Response error {}'.format(response.status_code))

            return False

    def _encode_unicode(self, s):
        if isinstance(s, unicode):
            return s.encode('utf-8')

        return s

    def _check_options(self, options, params):
        missing_options = set(params) - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        empty_options = [param for param in params if not options[param]]

        if empty_options:
            raise SitemapSpiderError('Empty options: {}'.format(', '.join(empty_options)))

    def _start_workers(self, func, count=10):
        workers = []
        tasks = mp.Queue()
        output = mp.Queue()

        for _ in range(count):
            thread = Thread(target=func, args=(tasks, output))
            thread.daemon = True
            thread.start()
            workers.append(thread)

        return workers, tasks, output

    def _stop_workers(self, workers, tasks):
        for _ in workers:
            tasks.put('STOP')

        for thread in workers:
            if thread.is_alive():
                thread.join(60)
