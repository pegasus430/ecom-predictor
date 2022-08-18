__author__ = 'root'

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
import json

def _find_between(s, first, last):
    try:
        start = s.index(first) + len(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""

levis_url = "http://www.levi.com/US/en_US/includes/searchResultsScroll/?nao={0}&url=%2FUS%2Fen_US%2Fcategory%2Fmen%2Fjeans%2Fall%2F_%2FN-2sZ1z13wzsZ8b8Z1z13x71Z1z140oj"

url_list = []

try:
    for index in range(1, 1000):
        print levis_url.format(index * 12 + 1)
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)

        page_html = html.fromstring(s.get(levis_url.format(index * 12 + 1), headers=h, timeout=5).text)
        urls = page_html.xpath("//div[@class='product-details']/a/@href")

        if not urls:
            break

        urls = ["http://www.levi.com" + url for url in urls]

        url_list.extend(urls)

    url_list = list(set(url_list))
    print "success"
except:
    print "fail"

url_list = list(set(url_list))

output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Levis/"

try:
    if os.path.isfile(output_dir_path + "urls.csv"):
        csv_file = open(output_dir_path + "urls.csv", 'a+')
    else:
        csv_file = open(output_dir_path + "urls.csv", 'w')

    csv_writer = csv.writer(csv_file)

    for product_url in url_list:
        row = [product_url]
        csv_writer.writerow(row)

    csv_file.close()
except:
    print "Error occurred"


print "success"
