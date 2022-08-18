import inspect
import traceback
import os
import urllib2
import json
import urllib
import copy
import logging
import zipfile

from importlib import import_module
from pkgutil import iter_modules


def load_downloaders(path):

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

    downloaders = {}

    for module in walk_modules(path):
        for obj in vars(module).itervalues():
            if inspect.isclass(obj)\
                    and issubclass(obj, ImageSubmissionDownloader)\
                    and obj.__module__ == module.__name__\
                    and getattr(obj, 'retailer', None):
                downloaders[obj.retailer] = obj

    return downloaders


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


class ImageSubmissionDownloaderError(Exception):
    pass


class ImageSubmissionDownloader(object):

    retailer = None  # retailer name, mandatory property

    def __init__(self, feed_id, resources_dir, logger=None):
        self.feed_id = feed_id
        self._results = []

        self._resources_dir = os.path.join(resources_dir, feed_id)
        if not os.path.exists(self._resources_dir):
            os.makedirs(self._resources_dir)

        self.logger = self._add_log_file(logger or logging.getLogger(__name__))

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

    def _api_url_iterator(self, server, criteria, differences_only=None):
        endpoint = server.get('endpoint') or '/api/products'

        if differences_only:
            endpoint += '/unmatched'

        apply_product_changes = server.get('apply_product_changes') or 1

        base_api_url = '{server}{endpoint}?' \
                       'product[apply_product_changes]={apply_product_changes}&' \
                       'api_key={api_key}&' \
                       '{params}'

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

    def _load_products(self, server, criteria, differences_only=None):
        products = []

        missing_fields = {'url', 'api_key'} - set(server.keys())
        if missing_fields:
            self.logger.error('Missing mandatory server fields: {}'.format(', '.join(missing_fields)))
        else:
            for url in self._api_url_iterator(server, criteria, differences_only):
                try:
                    self.logger.debug('Loading products: {}'.format(url))
                    res = urllib2.urlopen(url, timeout=60)
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

                            if differences_only and isinstance(data, list):
                                products.extend(data)
                            elif data.get('status') == 'error':
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

        products = None

        if server and criteria:
            products = self._load_products(server, criteria)

            if not products:
                return {'message': 'Products are not found'}

            if options.get('differences_only'):
                for differences in self._load_products(server, criteria, differences_only=True):
                    product = next((p for p in products if p.get('url') == differences.get('url')), None)

                    if product:
                        product.update({'differences': differences})

        message = None

        try:
            self.logger.info("Performing task '{}'".format(task_type))
            task(options, products=products)
        except ImageSubmissionDownloaderError as e:
            self.logger.error('Task {} error: {}'.format(task_type, traceback.format_exc()))
            message = e.message
        except:
            self.logger.error('Can not perform task ({}): {}'.format(task_type, traceback.format_exc()))
            message = 'Submission could not be processed'

        result = {
            'message': message,
            'results': self._save_results()
        }

        self.logger.info('Task result: {}'.format(result))

        return result

    def get_file_path_for_result(self, name=None, append=True):
        result_path = os.path.join(self._resources_dir, name)

        if append:
            self._results.append(result_path)

        return result_path

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
