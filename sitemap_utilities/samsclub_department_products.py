__author__ = 'root'

import re
import os
import time
import csv
import requests
import HTMLParser
import ast
import json
import xml.etree.ElementTree as ET
import urllib
from lxml import html, etree
import sys

department_url = "http://www.samsclub.com/sams/mattresses-mattress-sets/1350.cp?navTrack=gnav2_furniture_mattresses&navAction=jump"
page_raw_text = requests.get(department_url).text
page_tree_html = html.fromstring(page_raw_text)
child_departments_list = page_tree_html.xpath("//ul[@class='cfMarginL20 cfSubCategory']/li[@class='ctFilterBy']/a/@href")
load_items_per_page_number = 60
child_department_page_index_url = "http://www.samsclub.com/sams/shop/common/ajaxShelfPagePagination.jsp?brand=null&" \
                                  "altQuery={0}&" \
                                  "noOfRecordsPerPage={1}&" \
                                  "searchCategoryId={2}&" \
                                  "searchTerm=null&" \
                                  "viewStyle=null&" \
                                  "compareProducts=true&" \
                                  "offset={3}"

department_product_url_list = []

for child_department_url in child_departments_list:
    #http://www.samsclub.com/sams/king-mattresses/1352.cp?altQuery=100001_1285_1286_1350_1352&rootDimension=&navAction=push
    cp_id = re.findall ('/([0-9]+)\.cp?', child_department_url, re.DOTALL)[0]
    alt_query = re.findall ('altQuery=([0-9_]+)&?', child_department_url, re.DOTALL)[0]
    offset = 1

    while True:
        page_raw_text = requests.get(child_department_page_index_url.format(alt_query, load_items_per_page_number, cp_id, offset)).text
        page_tree_html = html.fromstring(page_raw_text)
        loaded_item_count = len(page_tree_html.xpath("//a[@class='shelfProdImgHolder']"))
        print loaded_item_count

        if loaded_item_count > 0:
            page_product_url_list = page_tree_html.xpath("//a[@class='shelfProdImgHolder']/@href")
            page_product_url_list = ["http://www.samsclub.com" + url for url in page_product_url_list]
            department_product_url_list.extend(page_product_url_list)

        if loaded_item_count < load_items_per_page_number:
            break

        offset += load_items_per_page_number

department_product_url_list = list(set(department_product_url_list))
print "Total product items: " + str(len(department_product_url_list))

output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Samsclub/"
try:
    csv_file = open(output_dir_path + "Mattresses products.csv", 'w')
    csv_writer = csv.writer(csv_file)

    for product_url in department_product_url_list:
        row = [product_url]
        csv_writer.writerow(row)

    csv_file.close()
except:
    print "Error occurred"