#
# Runs the given sc scraper locally and dumps the output URLs into a JSON-like format
#

from __future__ import print_function

import os
import sys
import json
import argparse

import requests


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('file', type=str,
                        help='Input file to read URLs from')
    parser.add_argument('output', type=str,
                        help='Output file to write URLs to')
    args = parser.parse_args()
    return args


def parse_url(url, print_file=sys.stdout):
    result = requests.get('http://localhost/get_data?url=%s' % url).text
    try:
        line = json.loads(result.strip())
    except Exception as e:
        line = {}
        line['ERROR'] = str(e)
    line['given_url'] = url
    print(json.dumps(line), file=print_file)
    print_file.flush()


if __name__ == '__main__':
    args = parse_args()
    urls = [l.strip() for l in open(args.file).readlines() if l.strip()]
    print_file = open(args.output, 'w')
    for url in urls:
        parse_url(url, print_file=print_file)