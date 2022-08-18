#
# Turns a list of UPCs into list of URLs (for Walmart.com)
#

import sys

import requests
import lxml.html


urls = [l.strip() for l in open(sys.argv[1], 'r').readlines() if l.strip()]

ids_only = 'ids_only' in sys.argv

for u in urls:
    walmart_url = 'http://www.walmart.com/search/?query=%s' % u
    walmart_content = requests.get(walmart_url).text
    walmart_doc = lxml.html.fromstring(walmart_content)

    href = walmart_doc.xpath('//a[contains(@class, "js-product-title")]/@href')
    if not href:
        print 'NOT FOUND'
        continue
    href = href[0]
    if href.startswith('/'):
        href = 'http://www.walmart.com' + href
    if ids_only:
        if '/' in href:
            href = href.rsplit('/', 1)[1].strip()
    print href
    sys.stdout.flush()