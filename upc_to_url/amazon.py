#
# Turns a list of UPCs into list of URLs (for Amazon.com)
#

import sys
import os
import json

import requests
import lxml.html


CWD = os.path.dirname(os.path.abspath(__file__))


urls = [l.strip() for l in open(sys.argv[1], 'r').readlines() if l.strip()]

output_fh = open(sys.argv[1] + '.output', 'w')

for u in urls:
    os.chdir(os.path.join(CWD, '..', 'product-ranking'))
    os.system('rm /tmp/amazon*')
    os.system('scrapy crawl amazon_products -a searchterms_str="%s" -a quantity=10 -o /tmp/amazon.jl' % u)

    with open('/tmp/amazon.jl') as fh:
        line = None
        for line in fh:
            line = json.loads(line.strip())

            if int(line['ranking']) == 1:
                break

        if not line:
            output_fh.write('NOT FOUND\n')
            continue

        url = line.get('url', None)
        output_fh.write(url + '\n')
        output_fh.flush()

        sys.stdout.flush()