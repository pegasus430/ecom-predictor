#
# Runs the given shelf_pages scraper locally and dumps the output URLs in to a CSV-like format
#

from __future__ import print_function

import os
import sys
import json
import argparse


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('spider', type=str,
                        help='Spider name')
    parser.add_argument('file', type=str,
                        help='Input file to read URLs from')
    parser.add_argument('output', type=str,
                        help='Output file to write URLs to')
    args = parser.parse_args()
    return args


def parse_url(spider, url, print_file=sys.stdout):
    _output_file = '/tmp/_output.jl'
    if os.path.exists(_output_file):
        os.remove(_output_file)
    os.system('scrapy crawl %s -a product_url="%s" -a num_pages=99999 -o "%s"' % (spider, url, _output_file))
    with open(_output_file) as fh:
        lines = [l.strip() for l in fh.readlines() if l.strip()]
    print(url, file=print_file)
    for line in lines:
        line = json.loads(line.strip())
        for _url, _prod_urls in line['assortment_url'].items():
            #print('    ', _url, file=print_file)
            for _prod_url in _prod_urls:
                print(';' + _prod_url, file=print_file)


if __name__ == '__main__':
    args = parse_args()
    urls = [l.strip() for l in open(args.file).readlines() if l.strip()]
    print_file = open(args.output, 'w')
    for url in urls:
        parse_url(args.spider, url, print_file=print_file)