__author__ = 'diogo'

import re
import os
import time
import csv
import sys
import requests
import xml.etree.ElementTree as ET

walmartca_sitemap_xml_link = "http://www.walmart.ca/sitemap-index-en.xml"
walmartca_sitemap_xml = requests.get(walmartca_sitemap_xml_link).text
walmartca_sitemap_xml = ET.fromstring(walmartca_sitemap_xml)
output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart CA CSV/"
file_name = "products.csv"
all_product_url_list = []

for walmart_department in walmartca_sitemap_xml:
    walmartca_sitemap_xml = requests.get(walmart_department[0].text.strip()).text
    walmartca_sitemap_xml = ET.fromstring(walmartca_sitemap_xml)

    for walmartca_product in walmartca_sitemap_xml:
        if not walmartca_product[0].text.startswith("http://www.walmart.ca/en/ip/"):
            continue

        all_product_url_list.append(walmartca_product[0].text.strip())

all_product_url_list = list(set(all_product_url_list))

try:
    if len(sys.argv) > 1:
        file_name = sys.argv[1] + ".csv"
    else:
        file_name = "products.csv"

    if os.path.isfile(output_dir_path + file_name):
        csv_file = open(output_dir_path + file_name, 'a+')
    else:
        csv_file = open(output_dir_path + file_name, 'w')

    csv_writer = csv.writer(csv_file)

    for product_url in all_product_url_list:
        row = [product_url]
        csv_writer.writerow(row)

    csv_file.close()
except:
    print "Error occurred"
