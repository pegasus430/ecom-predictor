# -*- coding: utf-8 -*-
# 11131 - LG.com - generate list of URLs

"""

Task #11131:

Build a script that will generate a list of product URLs on LG.com

Support 2 approaches:

1) Take in a list of model numbers (CSV file, one model number per line)
and use the search function on the site to find the corresponding URLs

2) Use sitemap to generate list from that

Return the list of URLs, one per line, in a CSV file.

******************************************************************************

Script usage:


1. extract all product URLs from the sitemap
$ python lg-scraper.py output-sitemap.csv

2. search for product URLs by their model numbers
$ python lg-scraper.py output-search.csv --input model-numbers.csv 

"""


__author__ = 'eduard.dev'
__desc__ = 'lg.com URLs scraper [#11131]'
__version__ = '0.1.0'

import os
import re
import csv
import urllib2
import logging
import argparse
from urllib import urlencode
from urlparse import urlparse
from random import choice, uniform
from time import sleep
from lxml.etree import fromstring
from lxml.html import document_fromstring


# search URL
SEARCH_URL = 'http://www.lg.com/us/search.lg'

# sitemap
SITEMAP_URL = 'http://www.lg.com/us/sitemap.xml'
SITEMAP_XMLNS = 'http://www.sitemaps.org/schemas/sitemap/0.9'


# network timeout
NETWORK_TIMEOUT = 60.0

# requests timeout (delay)
# * to prevent been banned
REQUEST_TIMEOUT = (1, 3)


# HTTP headers
DEFAULT_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# HTTP User-Agent header
USER_AGENTS = (
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:41.0) Gecko/20100101 Firefox/41.0',
    'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:42.0) Gecko/20100101 Firefox/42.0',
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.80 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11) AppleWebKit/601.1.56 (KHTML, like Gecko) Version/9.0 Safari/601.1.56',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_1) AppleWebKit/601.2.7 (KHTML, like Gecko) Version/9.0.1 Safari/601.2.7',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko',
)


# regexp
RE_NON_PRODUCT_URL = r'(specification|news|support|press|about)'

# XPATH selectors
XPATH_SEARCH_RESULTS = (
    '//li[@class="result-item"]'
    '//div[@class="type-product"]'
    '//a[@href]'
)


# logging config
LOG_TIME_FORMAT = '%H:%M:%S'
LOG_MSG_FORMAT = '%(asctime)s [%(levelname)s] %(message)s'
# 10: DEBUG, 20: INFO, 30: WARNING, 40: ERROR, 50: CRITICAL
LOG_LEVEL = 10



class Scraper(object):
    """
    LG.com URLs scraper
    """

    def http_request(self, url, data=None, headers=None, timeout=NETWORK_TIMEOUT):
        """
        make an HTTP GET or POST (if :data is set) request to URL 

        :param url: URL of the web resource {string}
        :param data: the POST data {dict}
        :param headers: extra HTTP headers {dict}
        :param timeout: network timeout {int}
        :return: response content {string}
        """

        if not isinstance(url, basestring):
            raise TypeError(':url must be string')
        elif data is not None and not isinstance(data, dict):
            raise TypeError(':data must be dict')
        elif headers is not None and not isinstance(headers, dict):
            raise TypeError(':headers must be dict')
        elif not isinstance(timeout, (int, float)):
            raise TypeError(':timeout must be int or float')

        req_type = ('GET', 'POST')[bool(data)]

        logging.debug('HTTP %s: %s' % (req_type, url))

        request = urllib2.Request(url)
        request.add_header('User-Agent', choice(USER_AGENTS))

        for header in DEFAULT_HEADERS:
            request.add_header(header, DEFAULT_HEADERS[header])

        if headers:
            for header in headers:
                request.add_header(header, headers[header])

        if data:
            data = urlencode(data)
        else:
            data = None

        try:
            r = urllib2.urlopen(request, data=data, timeout=timeout)

            status_code = r.getcode()
            if status_code != 200:
                raise Exception('Status code: %s' % status_code)

            response = r.read()
            return response

        except Exception as e:
            logging.error('HTTP %s [ %s ] :: %s' % (req_type, url, str(e)))


    def search(self, model):
        """
        search the product URL by the model data

        :param model: model number {string}
        :return: product URL or None (if not found)
        """
        if not isinstance(model, basestring):
            raise TypeError(':model must be string')

        search_page = self.http_request(
            SEARCH_URL,
            headers={
                'Referer': SEARCH_URL,
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            data={
                'search': model,
            }
        )
        if not search_page:
            return

        try:
            doc = document_fromstring(search_page)
        except Exception as e:
            logging.error('Unable to parse the search page: %s' % str(e))
            return

        search_results = doc.xpath(XPATH_SEARCH_RESULTS)
        if not search_results:
            logging.debug('No search results for [ %s ] model' % model)
            return

        url = search_results[0].get('href')

        if (
            not re.search(RE_NON_PRODUCT_URL, url, re.I) and
            len(urlparse(url).path.strip('/').split('/')) > 2 and
            re.search(r'\d', url)
        ):
            return url

        else:
            logging.debug('No product URL for [ %s ] model' % model)
            


    def parse_sitemap(self):
        """
        parse the sitemap and return all product URLs

        :yield: product URLs {string}
        """
        sitemap_xml = self.http_request(SITEMAP_URL)
        if not sitemap_xml:
            raise SystemExit

        urls_tree = {}

        try:
            doc = fromstring(sitemap_xml)
        except Exception as e:
            logging.error('Unable to parse the sitemap XML: %s' % str(e))
            raise SystemExit

        for url_node in doc.xpath(
            '//ns:url/ns:loc',
            namespaces={'ns': SITEMAP_XMLNS}
        ):
            url = url_node.text.strip()
            if (
                not re.search(RE_NON_PRODUCT_URL, url, re.I) and
                len(urlparse(url).path.strip('/').split('/')) > 2
            ):
                self.update_urls_tree(url, urls_tree)

        for url in self.extract_urls_from_tree(urls_tree):
            if re.search(r'\d', url):
                yield url


    # get endpoints (product URLs)  
    def extract_urls_from_tree(self, tree):
        """
        extract product URLs from the URLs tree

        :param tree: URLs tree {dict}
        :yield: product URLs {string}
        """
        for url, subtree in tree.iteritems():
            if not subtree:
                yield url
            else:
                for url in self.extract_urls_from_tree(subtree):
                    yield url


    # this method is used to find product URLs in the sitemap
    def update_urls_tree(self, url, tree):
        """
        update the URLs tree by finding all ancestors of the :url
        and binding the :url to the corresponding node

        :param url: URL to add {string}
        :param tree: URLs tree {dict}
        """
        for root_url, subtree in tree.iteritems():
            if url.startswith(root_url):
                if url != root_url:
                    self.update_urls_tree(url, subtree)
                return

        tree[url] = {}


    def run(self):
        """
        run the scraper
        """
        # parse CLI args
        args = self.parse_cli_args()

        logging.info('Starting %s v%s' % (__desc__, __version__))

        # prepare the output file
        output_file = os.path.abspath(args.output)
        if not output_file.endswith('.csv'):
            output_file = output_file + '.csv'

        # start
        with open(output_file, 'wb') as o_f:

            # CSV writer
            output_writer = csv.writer(o_f, quoting=csv.QUOTE_ALL)
            output_writer.writerow(['Product URL'])

            # if the --input file is set
            if args.input:
                logging.info('Searching for product URLs by their models')
 
                input_file = os.path.abspath(args.input)
                if not os.path.isfile(input_file):
                    logging.error(
                        'Unable to find the --input CSV file: %s'
                        % input_file
                    )

                else:
                    with open(input_file, 'rb') as i_f:
                        input_reader = csv.reader(i_f)

                        for row in input_reader:
                            if not row:
                                continue

                            prod_num = row[0]

                            url = self.search(prod_num)
                            if url:
                                output_writer.writerow([url])

                            sleep(uniform(*REQUEST_TIMEOUT))

            # otherwise process the sitemap
            else:
                logging.info('Searching for all product URLs in the sitemap')

                for url in self.parse_sitemap():
                    output_writer.writerow([url])

        logging.info('Done!')


    @staticmethod
    def parse_cli_args():
        """
        parse command-line arguments
        """
        argparser = argparse.ArgumentParser(description=__desc__)
        argparser.add_argument(
            'output',
            help='save product URLs into this CSV file'
        )
        argparser.add_argument(
            '-i', '--input',
            help='load product numbers from this CSV file'
        )
        return argparser.parse_args()
                



if __name__ == '__main__':

    # configure logging
    logging.basicConfig(
        format=LOG_MSG_FORMAT,
        datefmt=LOG_TIME_FORMAT,
        level=LOG_LEVEL,
    )

    # go
    scraper = Scraper()
    scraper.run()


