import requests
import urllib
import logging
import traceback
import time
from urlparse import urlsplit


def build_query_params(item):
    def recursion(_item, base=None):
        pairs = []
        if hasattr(_item, 'values'):
            for key, value in _item.iteritems():
                quoted_key = urllib.quote(unicode(key).encode('utf-8'))
                if base:
                    new_base = '{}[{}]'.format(base, quoted_key)
                else:
                    new_base = quoted_key
                pairs.extend(recursion(value, new_base))
        elif isinstance(_item, list):
            for index, value in enumerate(_item):
                if base:
                    new_base = "{}[{}]".format(base, index)
                    pairs.extend(recursion(value, new_base))
                else:
                    pairs.extend(recursion(value))
        else:
            quoted_item = urllib.quote(unicode(_item).encode('utf-8'))
            if _item is not None:
                if base:
                    pairs.append("{}={}".format(base, quoted_item))
                else:
                    pairs.append(quoted_item)
        return pairs

    return '&'.join(recursion(item))


class ImportAPI(object):
    PENDING = 1
    IN_PROGRESS = 2
    SUCCESS = 3
    FAILED = 4

    max_retries = 3

    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self._mc_api_keys = {}
        self.token = None

    def import_data(self, data):
        request_limit = 100

        for filename, products in data.iteritems():
            if self._get_token(filename):
                if self._set_status(self.IN_PROGRESS):
                    for i in range(0, len(products), request_limit):
                        self.logger.info('Sent {} products. Sending next 100...'.format(i))
                        if not self._import_products(products[i:i + request_limit]):
                            self._set_status(self.FAILED)
                            break
                    else:
                        self._set_status(self.SUCCESS)

    def _get_mc_api_key(self, server, username, password):
        if server not in self._mc_api_keys:
            self.logger.debug('Requesting API key for server {}'.format(server))
            api_url = 'https://{server}/api/token?username={username}&password={password}'.format(
                server=server, username=username, password=password)
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            self._mc_api_keys[server] = data['api_key']
        return self._mc_api_keys[server]

    def _get_token(self, filename):
        url = self.config['endpoint']['url']

        server = urlsplit(url).netloc
        username = self.config['endpoint']['username']
        password = self.config['endpoint']['password']

        response = None

        for i in range(1, self.max_retries + 1):
            try:
                if self.config.get('filename_as_customer', False):
                    customer = filename
                else:
                    customer = self.config['endpoint']['customer']
                data = {
                    'api_key': self._get_mc_api_key(server, username, password),
                    'file_name': filename,
                    'customer': customer
                }
                response = requests.post(
                    url,
                    data=build_query_params(data),
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                self.logger.debug('Get token response: {}'.format(response.content))

                if response.status_code == requests.codes.ok:
                    self.token = response.json().get('token')
                    return True
                else:
                    self.logger.error('Get token error: {}'.format(response.content))
            except:
                self.logger.error(
                    'Can not get token: {}, response: {}'.format(
                        traceback.format_exc(),
                        response.content if response else ''
                    )
                )
            self.logger.info('Try again in {} seconds'.format(i * 60))
            time.sleep(i * 60)
        return False

    def _set_status(self, status):
        url = self.config['endpoint']['url']

        server = urlsplit(url).netloc
        username = self.config['endpoint']['username']
        password = self.config['endpoint']['password']

        response = None

        for i in range(1, self.max_retries + 1):
            try:
                data = {
                    'api_key': self._get_mc_api_key(server, username, password),
                    'token': self.token,
                    'status': status
                }
                response = requests.put(
                    url,
                    data=build_query_params(data),
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                self.logger.debug('Set status response: {}'.format(response.content))

                if response.status_code == requests.codes.ok:
                    self.token = response.json().get('token')
                    return True
                else:
                    self.logger.error('Set status error: {}'.format(response.content))
            except:
                self.logger.error(
                    'Can not set status: {}, response: {}'.format(
                        traceback.format_exc(),
                        response.content if response else ''
                    )
                )
            if i < self.max_retries:
                self.logger.info('Try again in {} seconds'.format(i * 60))
                time.sleep(i * 60)

        return False

    def _import_products(self, products, modify_gtin=False):
        # fixme
        # parameter modify_gtin used for CON-37068 (Product Space files contains GTINs that differ from MC values)
        # currently we can't determine which products were not found with original gtin. So we calling that function
        # second time if all products wasn't found on MC
        if modify_gtin:
            for product in products:
                if product['id_type'] != 'gtin':
                    continue
                # sometimes we having float id values
                if not isinstance(product['id_value'], basestring):
                    try:
                        product['id_value'] = unicode(int(product['id_value']))
                    except:
                        self.logger.error(
                            'Product import error, bad id value. stacktrace: \n{}'.format(traceback.format_exc())
                        )
                        return False
                product['id_value'] = product['id_value'][:-1]  # removing "check digit"
                product['id_value'] = product['id_value'][:14].rjust(14, '0')  # gtin is 14 digits

        url = self.config['endpoint']['url'] + '/products'

        server = urlsplit(url).netloc
        username = self.config['endpoint']['username']
        password = self.config['endpoint']['password']

        response = None

        for i in range(1, self.max_retries + 1):
            try:
                data = {
                    'api_key': self._get_mc_api_key(server, username, password),
                    'token': self.token,
                    'products': products
                }
                response = requests.put(
                    url,
                    data=build_query_params(data),
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                self.logger.debug('Import products response: {}'.format(response.content))

                if response.status_code == requests.codes.ok:
                    r_json = response.json()
                    self.token = r_json.get('token')
                    # if all products failed with error "Product not found in Master Catalog." - retry a modified gtin
                    if not modify_gtin:
                        total = r_json.get('total', 0)
                        failed = r_json.get('failed', -1)
                        error_log = r_json.get('error_log', [])
                        error_log = [error for error in error_log if error == 'Product not found in Master Catalog.']
                        if total and total == failed == len(error_log):
                            self.logger.warning(
                                'Import: all products were not found on MC. Retrying with modified gtin.'
                            )
                            return self._import_products(products, modify_gtin=True)
                    return True
                else:
                    self.logger.error('Import products error: {}'.format(response.content))
            except:
                self.logger.error(
                    'Can not import products: {}, response: {}'.format(
                        traceback.format_exc(),
                        response.content if response else ''
                    )
                )
            self.logger.info('Try again in {} seconds'.format(i * 60))
            time.sleep(i * 60)

        return False
