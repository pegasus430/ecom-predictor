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

debenhams_site_url = "http://www.debenhams.com"
debenhams_sitemap_url = "http://www.debenhams.com/sitemap"

h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
s = requests.Session()
a = requests.adapters.HTTPAdapter(max_retries=3)
b = requests.adapters.HTTPAdapter(max_retries=3)
s.mount('http://', a)
s.mount('https://', b)
page_html = html.fromstring(s.get(debenhams_sitemap_url, headers=h, timeout=10).text)
category_urls = page_html.xpath("//div[@class='category']/ul//a/@href")
all_product_list = []

for category_url in category_urls:
    try:
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)
        category_page_html = html.fromstring(s.get(debenhams_site_url + category_url, headers=h, timeout=10).text)

        print debenhams_site_url + category_url

        product_urls = category_page_html.xpath("//div[@class='description']/a/@href")
        all_product_list.extend(product_urls)

        if category_page_html.xpath("//div[@id='pagination']"):
            for page_index in range(2, 1000):
                category_page_html = html.fromstring(s.get(debenhams_site_url + category_url + "?pn=" + str(page_index), headers=h, timeout=10).text)
                product_urls = category_page_html.xpath("//div[@class='description']/a/@href")

                if not product_urls:
                    break

                all_product_list.extend(product_urls)

                print debenhams_site_url + category_url + "?pn=" + str(page_index)
    except:
        continue

all_product_list = list(set(all_product_list))

for index, url in enumerate(all_product_list):
    if not url.startswith("http://"):
        all_product_list[index] = debenhams_site_url + url

output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Debenhams/"

try:
    if os.path.isfile(output_dir_path + "boots.csv"):
        csv_file = open(output_dir_path + "boots.csv", 'a+')
    else:
        csv_file = open(output_dir_path + "boots.csv", 'w')

    csv_writer = csv.writer(csv_file)

    for product_url in all_product_list:
        row = [product_url]
        csv_writer.writerow(row)

    csv_file.close()
except:
    print "Error occurred"


print "success"
