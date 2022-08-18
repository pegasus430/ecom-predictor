__author__ = 'diogo'

import re
import os
import time
import csv
import requests
import xml.etree.ElementTree as ET
from lxml import html, etree


uniqlo_site_url = "http://www.uniqlo.com"
site_html = html.fromstring(requests.get(uniqlo_site_url).text)
output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Uniqlo CSV/"
all_product_url_list = []

for department_block in site_html.xpath("//div[@class='parbase navDepartment section']"):
    for category_sub_url in department_block.xpath(".//div[contains(@class, 'secondary-nav group-list')]//li/a/@href"):
        category_url = uniqlo_site_url + category_sub_url
        category_html = html.fromstring(requests.get(category_url).text)
        category_product_url_list = category_html.xpath("//div[contains(@class, 'product-tile-component enable-quick-view')]//a[1]/@href")
        subsidiary_category_list = category_html.xpath("//ul[@class='breadcrumb-component']/li/a/text()")

        '''
        category_text = ""

        for index, item_text in enumerate(subsidiary_category_list):
            category_text = category_text + item_text.strip()

            if index + 1 < len(subsidiary_category_list):
                category_text = category_text + "/"
        '''

        for index, product_url in enumerate(category_product_url_list):
            if product_url.endswith(".html"):
                continue
            else:
                url = product_url
                url = uniqlo_site_url + url[:url.find(".html#") + 5]
                category_product_url_list[index] = url

        all_product_url_list.extend(category_product_url_list)

all_product_url_list = list(set(all_product_url_list))

try:
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
