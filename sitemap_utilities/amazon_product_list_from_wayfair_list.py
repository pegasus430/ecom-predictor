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
import urllib
from lxml import html, etree
import sys

search_url_by_id = "http://www.amazon.com/s/ref=nb_sb_noss_2?url=search-alias%3Daps&field-keywords={0}"
product_url_list = []

intput_file = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Amazon/wayfair.csv"
f1 = open(intput_file)
csv_f = csv.reader(f1)
wayfair_product_list = list(csv_f)

wayfair_product_list = [row[0] for row in wayfair_product_list]

output_file = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Amazon/wayfair_amazon.csv"

if os.path.isfile(output_file):
    csv_file = open(output_file, 'a+')
else:
    csv_file = open(output_file, 'w')

csv_writer = csv.writer(csv_file)

wayfair_amazon_product_list = []

for wayfair_url in wayfair_product_list:
    try:
        id = wayfair_url[wayfair_url.rfind("-", 0, wayfair_url.rfind("-")) + 1:wayfair_url.rfind("-")]
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)
        product_html = html.fromstring(s.get(search_url_by_id.format("wayfair+" + id), headers=h, timeout=5).text)
        amazon_url = product_html.xpath("//ul[@id='s-results-list-atf']//div[@class='s-item-container']//a[@class='a-link-normal s-access-detail-page  a-text-normal']/@href")[0]
        amazon_url = amazon_url[:amazon_url.find("/ref=")]
        row = [wayfair_url, amazon_url]
        wayfair_amazon_product_list.append(row)
        csv_writer.writerow(row)
    except:
        print "fail"
        continue

product_url_list = list(set(product_url_list))

csv_file.close()
