__author__ = 'root'

import re
import os
import time
import csv
import requests
import zlib
import xml.etree.ElementTree as ET
from xml.dom.minidom import parse, parseString

marksandspencer_product_sitemap_xml_links = ["http://www.marksandspencer.com/sitemap_10151_1.xml.gz"]
product_list = []
output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Marks and Spencer/products.csv"

sitemap_file = open('/home/mufasa/Documents/Workspace/Content Analytics/Misc/Marks and Spencer/sitemap_10151_1.xml')
sitemap_xml = sitemap_file.read()

product_list.extend(re.findall('<loc>(.*?)</loc>', sitemap_xml, re.DOTALL))

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