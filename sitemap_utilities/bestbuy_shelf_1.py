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

shelf_urls_list = ["http://www.bestbuy.com/site/all-laptops/2-in-1-laptops/pcmcat309300050015.c?id=pcmcat309300050015&nrp=15&cp={0}&sp=-bestsellingsort%20skuidsaas",
                   "http://www.bestbuy.com/site/computer-accessories/hard-drives/abcat0504001.c?id=abcat0504001&nrp=15&cp={0}&sp=-bestsellingsort%20skuidsaas",
                   "http://www.bestbuy.com/site/computers-pcs/networking/abcat0503000.c?id=abcat0503000&nrp=15&cp={0}&sp=-bestsellingsort%20skuidsaas"]

url_list = []

for shelf_url in shelf_urls_list:
    try:
        print shelf_url
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)

        for index in range(1, 100000):
            page_html = html.fromstring(s.get(shelf_url.format(index), headers=h, timeout=5).text)

            if not page_html.xpath("//div[@class='number-of-items']/strong/text()"):
                break

            urls = page_html.xpath("//div[@class='sku-title']//a/@href")
            urls = ["http://www.bestbuy.com" + url for url in urls]
            url_list.extend(urls)
        print "success"
    except:
        print "fail"

url_list = list(set(url_list))

output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Bestbuy from Shelf/"

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
