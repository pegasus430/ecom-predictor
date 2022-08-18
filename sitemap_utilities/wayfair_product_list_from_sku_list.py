__author__ = 'root'

#Bug 3481 - Generate list of Wayfair URLs from SKU numbers (edit)

import re
import os
import time
import csv
import requests
import HTMLParser
import ast
import xml.etree.ElementTree as ET
from lxml import html, etree
import sys

search_url_by_sku = "http://www.wayfair.com/keyword.php?keyword={0}&ust=&command=dosearch&new_keyword_search=true"
product_url_list = []

output_file = "products.csv"

if os.path.isfile(output_file):
    csv_file = open(output_file, 'a+')
else:
    csv_file = open(output_file, 'w')

csv_writer = csv.writer(csv_file)

for index in range(0, 999):
    try:
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)
        product_html = html.fromstring(s.get(search_url_by_sku.format("HTJ5" + str(index).zfill(3)), headers=h, timeout=5).text)
        print product_html.xpath("//link[@rel='canonical']/@href")[0]
        product_url_list.append(product_html.xpath("//link[@rel='canonical']/@href")[0])
        row = [product_html.xpath("//link[@rel='canonical']/@href")[0]]
        csv_writer.writerow(row)
    except:
        print "fail"
        continue

product_url_list = list(set(product_url_list))

csv_file.close()
