__author__ = 'diogo'

import re
import os
import time
import csv
import requests
import ast
import xml.etree.ElementTree as ET
from lxml import html, etree
import sys

freshdirect_site_url = "https://www.freshdirect.com"
output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Freshdirect CSV/"

all_product_url_list = []

site_html = html.fromstring(requests.get(freshdirect_site_url).text)
category_url_list = site_html.xpath("//div[@class='dropdown-column']/ul/li/a/@href")
category_url_list = list(set(category_url_list))
category_url_pattern = "https://www.freshdirect.com/browse.jsp?pageType=browse&id={}&pageSize=30&all=true&activePage=0&sortBy=Sort_ExpertRatingHigh&orderAsc=true&activeTab=product"

for category_url in category_url_list:
    try:
        category_id = category_url[category_url.rfind("?id=") + 4:]
        print category_id

        category_url = category_url_pattern.format(category_id)
        category_html = html.fromstring(requests.get(category_url).text)
        product_url_list = category_html.xpath("//div[@class='browseContent']//div[@class='portrait-item-header']/a/@href")
        product_url_list = [freshdirect_site_url + url for url in product_url_list]
        all_product_url_list.extend(product_url_list)
    except:
        print "Failed: " + category_id

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
