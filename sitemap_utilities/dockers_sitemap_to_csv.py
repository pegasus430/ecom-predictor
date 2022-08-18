__author__ = 'root'

import re
import os
import time
import csv
import requests
import xml.etree.ElementTree as ET

output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Dockers/products.csv"

sitemap_file = open('/home/mufasa/Downloads/dockers-sitemap-US.xml')
sitemap_xml = sitemap_file.read()

product_list = (re.findall('<loc>(.*?)</loc>', sitemap_xml, re.DOTALL))

product_list = [url for url in product_list if "/p/" in url]
product_list = list(set(product_list))

print len(product_list)

for url in product_list:
    try:
        url = url.strip()

        if os.path.isfile(output_dir_path):
            csv_file = open(output_dir_path, 'a+')
        else:
            csv_file = open(output_dir_path, 'w')

        csv_writer = csv.writer(csv_file)

        row = [url]
        csv_writer.writerow(row)
        csv_file.close()
    except:
        print url
        continue